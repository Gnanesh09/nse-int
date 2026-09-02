from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (
    FastAPI,
    HTTPException,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
)

from .ai import analyze
from .config import settings
from .db import (
    announcements,
    get_announcement,
    get_all_watched_symbols,
    get_recent_announcements,
    get_user,
    get_users_for_symbol,
    init_db,
    insert_announcement,
    now_utc,
    ping_db,
    update_announcement_analysis,
    upsert_user,
)
from .emailer import (
    send_email,
    send_test_email,
    send_watchlist_digest,
)
from .nse import (
    NSEClient,
    extract_pdf_text,
    fetch_recent,
    normalize_announcement,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
)

log = logging.getLogger(
    "south-decan-capital"
)


# =========================================================
# APP STATE
# =========================================================

poll_lock = asyncio.Lock()


# =========================================================
# MODELS
# =========================================================

class WatchRequest(BaseModel):

    email: EmailStr

    symbols: list[str] = Field(
        default_factory=list,
        max_length=200,
    )


class PollResponse(BaseModel):

    fetched: int = 0

    matched: int = 0

    new: int = 0

    analyzed: int = 0

    emailed: int = 0

    failed: int = 0


# =========================================================
# CORS
# =========================================================

origins = [

    origin.strip()

    for origin in settings.cors_origins.split(
        ","
    )

    if origin.strip()
]


# =========================================================
# POLL / PROCESS
# =========================================================

async def process_announcement(
    announcement: dict,
    email_users: bool = True,
) -> tuple[bool, bool]:

    """
    Returns:
        analyzed_now, email_success_for_any_user
    """

    # -----------------------------------------------------
    # Existing DB record?
    # -----------------------------------------------------

    existing = await asyncio.to_thread(
        get_announcement,
        announcement["nse_id"],
    )


    # -----------------------------------------------------
    # If already analyzed, don't spend Groq tokens again.
    # -----------------------------------------------------

    if existing and existing.get(
        "analysis"
    ):

        announcement = existing

        analysis = existing[
            "analysis"
        ]

        analyzed_now = False


    else:

        announcement[
            "first_seen_at"
        ] = now_utc()

        announcement[
            "analyzed"
        ] = False

        announcement[
            "emailed_to"
        ] = []


        inserted = await asyncio.to_thread(
            insert_announcement,
            announcement,
        )


        # Another process may already
        # have inserted this announcement.
        if not inserted:

            existing = await asyncio.to_thread(
                get_announcement,
                announcement["nse_id"],
            )


            if (
                existing
                and existing.get(
                    "analysis"
                )
            ):

                announcement = (
                    existing
                )

                analysis = (
                    existing["analysis"]
                )

                analyzed_now = False

            else:

                raise RuntimeError(
                    "Announcement exists but "
                    "has no completed analysis."
                )

        else:

            # -------------------------------------------------
            # PDF
            # -------------------------------------------------

            filing_text = await asyncio.to_thread(
                extract_pdf_text,
                announcement.get(
                    "attachment_url"
                ),
            )


            log.info(
                "Analyzing %s | PDF chars=%s",
                announcement.get(
                    "symbol"
                ),
                len(filing_text),
            )


            # -------------------------------------------------
            # GROQ / LANGGRAPH
            # -------------------------------------------------

            ai_result = await asyncio.to_thread(
                analyze,
                announcement,
                filing_text,
            )


            analysis = ai_result[
                "analysis"
            ]

            usage = ai_result.get(
                "usage",
                {},
            )


            # -------------------------------------------------
            # STORE EVERYTHING EXCEPT FULL RAW PDF TEXT
            # -------------------------------------------------

            await asyncio.to_thread(

                update_announcement_analysis,

                announcement[
                    "nse_id"
                ],

                analysis,

                usage,
            )


            # We intentionally don't put the
            # entire filing text in MongoDB
            # in this version.

            analyzed_now = True


    # -----------------------------------------------------
    # INDIVIDUAL EMAIL
    # -----------------------------------------------------

    email_success = False


    if email_users:

        users = await asyncio.to_thread(
            get_users_for_symbol,
            announcement[
                "symbol"
            ],
        )


        for user in users:

            user_email = (
                user["email"]
            )


            try:

                await asyncio.to_thread(
                    send_email,
                    user_email,
                    announcement,
                    analysis,
                )


                await asyncio.to_thread(

                    announcements.update_one,

                    {
                        "nse_id":
                            announcement[
                                "nse_id"
                            ]
                    },

                    {
                        "$addToSet":
                        {
                            "emailed_to":
                                user_email
                        }
                    },
                )


                email_success = True


            except Exception:

                log.exception(
                    "Email failed: %s -> %s",
                    announcement.get(
                        "symbol"
                    ),
                    user_email,
                )


    return (
        analyzed_now,
        email_success,
    )


# =========================================================
# POLL
# =========================================================

async def poll_once() -> PollResponse:

    async with poll_lock:

        client = NSEClient(
            timeout=
                settings.nse_timeout_seconds,

            max_retries=
                settings.nse_max_retries,
        )


        try:

            watched = await asyncio.to_thread(
                get_all_watched_symbols
            )


            if not watched:

                return PollResponse()


            raw = await asyncio.to_thread(
                fetch_recent,
                client,
                settings.nse_lookback_minutes,
            )


            response = PollResponse(
                fetched=len(raw)
            )


            for raw_item in raw:

                announcement = (
                    normalize_announcement(
                        raw_item
                    )
                )


                symbol = (
                    announcement[
                        "symbol"
                    ]
                )


                if (
                    not symbol
                    or symbol not in watched
                ):

                    continue


                response.matched += 1


                try:

                    existing = await asyncio.to_thread(
                        get_announcement,
                        announcement[
                            "nse_id"
                        ],
                    )


                    if (
                        existing
                        and existing.get(
                            "analysis"
                        )
                    ):

                        continue


                    response.new += 1


                    analyzed, emailed = (
                        await process_announcement(
                            announcement,
                            email_users=True,
                        )
                    )


                    if analyzed:

                        response.analyzed += 1


                    if emailed:

                        response.emailed += 1


                except Exception:

                    response.failed += 1


                    log.exception(
                        "Processing failed for NSE ID %s",
                        announcement.get(
                            "nse_id"
                        ),
                    )


            return response


        finally:

            client.close()


# =========================================================
# SCHEDULER
# =========================================================

async def scheduler_loop():

    log.info(
        "South Decan Capital scheduler started"
    )


    while True:

        try:

            result = await poll_once()


            log.info(
                (
                    "NSE poll | fetched=%s "
                    "matched=%s new=%s "
                    "analyzed=%s emailed=%s "
                    "failed=%s"
                ),
                result.fetched,
                result.matched,
                result.new,
                result.analyzed,
                result.emailed,
                result.failed,
            )


        except asyncio.CancelledError:

            raise


        except Exception:

            log.exception(
                "Background NSE poll failed"
            )


        await asyncio.sleep(
            settings.nse_poll_seconds
        )


# =========================================================
# LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    init_db()


    scheduler_task = None


    if settings.scheduler_enabled:

        scheduler_task = (
            asyncio.create_task(
                scheduler_loop()
            )
        )


    yield


    if scheduler_task:

        scheduler_task.cancel()

        try:

            await scheduler_task

        except asyncio.CancelledError:

            pass


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(

    title=(
        "South Decan Capital "
        "NSE Corporate Intelligence"
    ),

    version=settings.app_version,

    description=(
        "AI-assisted NSE corporate-filings "
        "intelligence platform."
    ),

    lifespan=lifespan,
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    db_ok = ping_db()

    return {

        "ok":
            db_ok,

        "service":
            settings.app_name,

        "version":
            settings.app_version,

        "utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "database":
            "up" if db_ok else "down",

        "groq":
            "configured"
            if settings.groq_api_key
            else "missing",

        "smtp":
            "configured"
            if all(
                [
                    settings.smtp_host,
                    settings.smtp_user,
                    settings.smtp_password,
                    settings.smtp_from,
                ]
            )
            else "missing",
    }


# =========================================================
# WATCHLIST
# =========================================================
@app.get(
    "/nse",
    response_class=HTMLResponse,
)
async def nse_dashboard():

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():

        raise HTTPException(
            status_code=500,
            detail=(
                "Frontend file not found: "
                f"{index_file}"
            ),
        )

    return HTMLResponse(
        content=index_file.read_text(
            encoding="utf-8"
        )
    )
    
    
    
@app.post("/watch")
def watch(
    request: WatchRequest,
):

    symbols = sorted(

        {
            symbol.strip().upper()

            for symbol in request.symbols

            if symbol
            and symbol.strip()
        }
    )


    if not symbols:

        raise HTTPException(
            status_code=400,
            detail=(
                "Provide at least one NSE symbol."
            ),
        )


    user = upsert_user(
        request.email,
        symbols,
    )


    return {

        "email":
            user.get(
                "email",
                str(request.email),
            ),

        "symbols":
            user.get(
                "symbols",
                symbols,
            ),

        "updated_at":
            user.get(
                "updated_at"
            ),
    }


# =========================================================
# GET WATCHLIST
# =========================================================

@app.get(
    "/watch/{email}"
)
def get_watch(
    email: str,
):

    user = get_user(
        email
    )


    if not user:

        raise HTTPException(
            status_code=404,
            detail="Watcher not found.",
        )


    return user


# =========================================================
# ANNOUNCEMENTS
# =========================================================

@app.get(
    "/announcements/{symbol}"
)
def recent_announcements(
    symbol: str,
    limit: int = 20,
):

    return get_recent_announcements(
        symbol,
        limit,
    )


# =========================================================
# MANUAL POLL
# =========================================================

@app.post(
    "/poll",
    response_model=PollResponse,
)
async def manual_poll():

    return await poll_once()


# =========================================================
# WATCHLIST AI REPORT
# =========================================================

@app.post(
    "/send-watchlist-analysis/{email}"
)
async def send_watchlist_analysis(
    email: str,
):

    user = get_user(
        email
    )


    if not user:

        raise HTTPException(
            status_code=404,
            detail="Watcher not found.",
        )


    symbols = {
        symbol.upper()
        for symbol in user.get(
            "symbols",
            [],
        )
    }


    if not symbols:

        raise HTTPException(
            status_code=400,
            detail="Watcher has no symbols.",
        )


    # -----------------------------------------------------
    # SMTP validation FIRST.
    #
    # This prevents expensive Groq processing when email
    # configuration is missing.
    # -----------------------------------------------------

    if not all(
        [
            settings.smtp_host,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_from,
        ]
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "SMTP is not configured. "
                "Set SMTP_HOST, SMTP_USER, "
                "SMTP_PASSWORD and SMTP_FROM."
            ),
        )


    # -----------------------------------------------------
    # Fetch
    # -----------------------------------------------------

    client = NSEClient(
        timeout=settings.nse_timeout_seconds,
        max_retries=settings.nse_max_retries,
    )


    selected = []

    analyzed_now = 0

    failed = 0


    try:

        raw = await asyncio.to_thread(
            fetch_recent,
            client,
            settings.nse_lookback_minutes,
        )


        for raw_item in raw:

            announcement = (
                normalize_announcement(
                    raw_item
                )
            )


            if (
                not announcement[
                    "symbol"
                ]
                or announcement[
                    "symbol"
                ] not in symbols
            ):

                continue


            try:

                existing = await asyncio.to_thread(
                    get_announcement,
                    announcement[
                        "nse_id"
                    ],
                )


                if (
                    existing
                    and existing.get(
                        "analysis"
                    )
                ):

                    announcement = (
                        existing
                    )

                    analysis = (
                        existing[
                            "analysis"
                        ]
                    )


                else:

                    # -------------------------------------------------
                    # New announcement
                    # -------------------------------------------------

                    announcement[
                        "first_seen_at"
                    ] = now_utc()

                    announcement[
                        "analyzed"
                    ] = False

                    announcement[
                        "emailed_to"
                    ] = []


                    inserted = await asyncio.to_thread(
                        insert_announcement,
                        announcement,
                    )


                    if not inserted:

                        existing = await asyncio.to_thread(
                            get_announcement,
                            announcement[
                                "nse_id"
                            ],
                        )


                        if (
                            existing
                            and existing.get(
                                "analysis"
                            )
                        ):

                            announcement = (
                                existing
                            )

                            analysis = (
                                existing[
                                    "analysis"
                                ]
                            )

                        else:

                            raise RuntimeError(
                                "Announcement was "
                                "already inserted but "
                                "has no analysis."
                            )


                    else:

                        filing_text = await asyncio.to_thread(
                            extract_pdf_text,
                            announcement.get(
                                "attachment_url"
                            ),
                        )


                        ai_result = (
                            await asyncio.to_thread(
                                analyze,
                                announcement,
                                filing_text,
                            )
                        )


                        analysis = (
                            ai_result[
                                "analysis"
                            ]
                        )


                        await asyncio.to_thread(

                            update_announcement_analysis,

                            announcement[
                                "nse_id"
                            ],

                            analysis,

                            ai_result.get(
                                "usage",
                                {},
                            ),
                        )


                        analyzed_now += 1


                selected.append(
                    {
                        "announcement":
                            announcement,

                        "analysis":
                            analysis,
                    }
                )


            except Exception:

                failed += 1

                log.exception(
                    "Watchlist report processing failed for %s",
                    announcement.get(
                        "nse_id"
                    ),
                )


    finally:

        client.close()


    if not selected:

        raise HTTPException(
            status_code=404,
            detail=(
                "No announcements found "
                "for today's watched symbols: "
                f"{sorted(symbols)}"
            ),
        )


    # -----------------------------------------------------
    # ONE CONSOLIDATED EMAIL
    # -----------------------------------------------------

    await asyncio.to_thread(

        send_watchlist_digest,

        email.strip().lower(),

        selected,
    )


    return {

        "ok": True,

        "email":
            email.strip().lower(),

        "symbols":
            sorted(symbols),

        "announcements_found":
            len(selected),

        "analyzed_now":
            analyzed_now,

        "failed":
            failed,

        "email_sent":
            True,
    }


# =========================================================
# SMTP TEST
# =========================================================

class TestEmailRequest(
    BaseModel
):

    email: EmailStr


@app.post(
    "/test-email"
)
async def test_email(
    request: TestEmailRequest,
):

    if not all(
        [
            settings.smtp_host,
            settings.smtp_user,
            settings.smtp_password,
            settings.smtp_from,
        ]
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "SMTP is not configured."
            ),
        )


    try:

        await asyncio.to_thread(
            send_test_email,
            str(request.email),
        )


        return {

            "ok": True,

            "email":
                str(request.email),

            "message":
                "Test email sent.",
        }


    except Exception as exc:

        log.exception(
            "SMTP test failed"
        )


        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )
        
        