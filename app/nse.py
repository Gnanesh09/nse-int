from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import httpx


NSE_HOME = (
    "https://www.nseindia.com/"
)

NSE_API = (
    "https://www.nseindia.com/"
    "api/corporate-announcements"
)

NSE_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-announcements"
)

NSE_ARCHIVE_BASE = (
    "https://nsearchives.nseindia.com/"
)


HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),

    "Accept": (
        "application/json,"
        "text/plain,*/*"
    ),

    "Accept-Language": (
        "en-US,en;q=0.9"
    ),

    "Referer": NSE_PAGE,

    "Origin": (
        "https://www.nseindia.com"
    ),

    "Connection": "keep-alive",
}


# =========================================================
# NSE CLIENT
# =========================================================

class NSEClient:

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 4,
    ):

        self.max_retries = max_retries

        self.client = httpx.Client(
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )


    def close(self):

        self.client.close()


    def warmup(self):

        """
        Best-effort warm-up.

        NSE can return 403 for the homepage while the API
        itself remains reachable. Therefore this must NEVER
        make the collector fail.
        """

        try:

            response = self.client.get(
                NSE_HOME
            )

            if response.status_code == 200:

                return True

            return False

        except Exception:

            return False


    def fetch(
        self,
        from_date: str,
        to_date: str,
        symbol: str | None = None,
    ) -> list[dict]:

        params = {

            "index": "equities",

            "from_date": from_date,

            "to_date": to_date,
        }

        if symbol:

            params["symbol"] = (
                symbol.upper()
            )


        last_error = None


        # Warm-up is intentionally best effort.
        self.warmup()


        for attempt in range(
            self.max_retries
        ):

            try:

                response = self.client.get(
                    NSE_API,
                    params=params,
                )


                if response.status_code in (
                    403,
                    429,
                    500,
                    502,
                    503,
                    504,
                ):

                    raise httpx.HTTPStatusError(
                        (
                            "NSE request failed with "
                            f"HTTP {response.status_code}"
                        ),
                        request=response.request,
                        response=response,
                    )


                response.raise_for_status()


                payload = response.json()


                if isinstance(
                    payload,
                    list,
                ):

                    return payload


                if isinstance(
                    payload,
                    dict,
                ):

                    for key in (
                        "data",
                        "results",
                        "records",
                    ):

                        value = payload.get(
                            key
                        )

                        if isinstance(
                            value,
                            list,
                        ):

                            return value


                raise ValueError(
                    "Unexpected NSE response shape"
                )


            except Exception as exc:

                last_error = exc

                if attempt >= (
                    self.max_retries - 1
                ):

                    break


                delay = (
                    2 ** attempt
                    + random.uniform(
                        0.25,
                        1.25,
                    )
                )

                time.sleep(delay)


        raise RuntimeError(
            "NSE fetch failed after "
            f"{self.max_retries} attempts: "
            f"{last_error}"
        )


# =========================================================
# NORMALIZATION
# =========================================================

def _first(
    raw: dict,
    *keys: str,
):

    for key in keys:

        value = raw.get(
            key
        )

        if value not in (
            None,
            "",
        ):

            return value

    return None


def _parse_datetime(
    value,
) -> datetime | None:

    if not value:

        return None


    text = str(
        value
    ).strip()


    formats = [

        "%d-%b-%Y %H:%M:%S",

        "%d-%b-%Y %H:%M:%S.%f",

        "%d-%m-%Y %H:%M:%S",

        "%Y-%m-%d %H:%M:%S",

        "%Y-%m-%dT%H:%M:%S",

        "%Y-%m-%dT%H:%M:%S.%f",

    ]


    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt,
            )

        except ValueError:

            continue


    return None


def normalize_announcement(
    raw: dict,
) -> dict:

    symbol = _first(
        raw,
        "symbol",
        "sym",
    )

    company = _first(
        raw,
        "companyName",
        "company",
        "companyname",
    )

    subject = _first(
        raw,
        "subject",
        "desc",
        "description",
    )

    details = _first(
        raw,
        "attchmntText",
        "details",
        "detail",
        "desc",
        "description",
    )

    attachment = _first(
        raw,
        "attchmntFile",
        "attachment",
        "attachmentFile",
        "fileName",
    )

    broadcast = _first(
        raw,
        "an_dt",
        "broadcastDateTime",
        "broadcastDate",
        "broadCastDate",
    )


    if attachment:

        attachment = urljoin(
            NSE_ARCHIVE_BASE,
            str(attachment),
        )


    nse_id = _first(
        raw,
        "seq_id",
        "seqId",
        "id",
        "sno",
    )


    if not nse_id:

        nse_id = (
            f"{symbol}|"
            f"{broadcast}|"
            f"{subject}|"
            f"{attachment}"
        )


    return {

        "nse_id": str(
            nse_id
        ),

        "symbol": (
            str(symbol or "")
            .strip()
            .upper()
        ),

        "company": (
            str(company or "")
            .strip()
        ),

        "subject": (
            str(subject or "")
            .strip()
        ),

        "details": (
            str(details or "")
            .strip()
        ),

        "attachment_url": attachment,

        "broadcast_raw": broadcast,

        "broadcast_dt": _parse_datetime(
            broadcast
        ),

        "raw": raw,
    }


# =========================================================
# PDF
# =========================================================

def extract_pdf_text(
    url: str,
) -> str:

    if not url:

        return ""


    try:

        response = httpx.get(

            url,

            headers={
                "User-Agent":
                    HEADERS["User-Agent"],

                "Referer":
                    NSE_PAGE,
            },

            timeout=45,

            follow_redirects=True,
        )


        response.raise_for_status()


        content_type = (
            response.headers
            .get(
                "content-type",
                "",
            )
            .lower()
        )


        if (
            "pdf"
            not in content_type
            and not response.content.startswith(
                b"%PDF"
            )
        ):

            return ""


        import fitz


        pdf = fitz.open(
            stream=response.content,
            filetype="pdf",
        )


        pages = []


        for page in pdf:

            text = page.get_text(
                "text"
            )

            if text and text.strip():

                pages.append(
                    text.strip()
                )


        pdf.close()


        return "\n\n".join(
            pages
        ).strip()


    except Exception as exc:

        print(
            "PDF extraction failed:",
            url,
            exc,
        )

        return ""


# =========================================================
# RECENT DATA
# =========================================================

def fetch_recent(
    client: NSEClient,
    lookback_minutes: int,
):

    now = datetime.now(
        timezone.utc
    )

    start = (
        now
        - timedelta(
            minutes=lookback_minutes
        )
    )


    return client.fetch(

        start.strftime(
            "%d-%m-%Y"
        ),

        now.strftime(
            "%d-%m-%Y"
        ),
    )