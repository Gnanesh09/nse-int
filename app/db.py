from __future__ import annotations

from datetime import datetime, timezone

from pymongo import (
    ASCENDING,
    DESCENDING,
    MongoClient,
)
from pymongo.errors import DuplicateKeyError

from .config import settings


# =========================================================
# CONNECTION
# =========================================================

client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=15000,
)

db = client[settings.mongodb_db]

announcements = db["announcements"]
users = db["users"]


# =========================================================
# TIME
# =========================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================
def init_db() -> None:

    # ---------------------------------------------------------
    # Announcements
    # ---------------------------------------------------------

    # Existing MongoDB installations may already have:
    # nse_id_1
    #
    # Do not attempt to create another unique index over
    # the same field with a different name.
    announcements.create_index(
        [("nse_id", ASCENDING)],
        unique=True,
    )

    announcements.create_index(
        [
            ("symbol", ASCENDING),
            ("broadcast_dt", DESCENDING),
        ],
        name="idx_symbol_broadcast",
    )

    announcements.create_index(
        [
            ("symbol", ASCENDING),
            ("analyzed", ASCENDING),
            ("broadcast_dt", DESCENDING),
        ],
        name="idx_symbol_analyzed",
    )

    announcements.create_index(
        [("first_seen_at", DESCENDING)],
        name="idx_first_seen",
    )

    # ---------------------------------------------------------
    # Users
    # ---------------------------------------------------------

    users.create_index(
        [("email", ASCENDING)],
        unique=True,
    )

    users.create_index(
        [("symbols", ASCENDING)],
        name="idx_user_symbols",
    )

# =========================================================
# HEALTH
# =========================================================

def ping_db() -> bool:

    try:

        client.admin.command("ping")

        return True

    except Exception:

        return False


# =========================================================
# USERS
# =========================================================

def upsert_user(
    email: str,
    symbols: list[str],
) -> dict:

    normalized_email = (
        email.strip().lower()
    )

    normalized_symbols = sorted(
        {
            symbol.strip().upper()
            for symbol in symbols
            if symbol and symbol.strip()
        }
    )

    now = now_utc()

    users.update_one(
        {
            "email": normalized_email,
        },
        {
            "$set": {
                "email": normalized_email,
                "symbols": normalized_symbols,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    return get_user(normalized_email) or {}


def get_user(
    email: str,
) -> dict | None:

    return users.find_one(
        {
            "email": email.strip().lower(),
        },
        {
            "_id": 0,
        },
    )


def get_all_watched_symbols() -> set[str]:

    symbols: set[str] = set()

    cursor = users.find(
        {},
        {
            "_id": 0,
            "symbols": 1,
        },
    )

    for user in cursor:

        for symbol in user.get(
            "symbols",
            [],
        ):

            if symbol:

                symbols.add(
                    symbol.upper()
                )

    return symbols


def get_users_for_symbol(
    symbol: str,
) -> list[dict]:

    return list(
        users.find(
            {
                "symbols": symbol.upper(),
            },
            {
                "_id": 0,
                "email": 1,
                "symbols": 1,
            },
        )
    )


# =========================================================
# ANNOUNCEMENTS
# =========================================================

def insert_announcement(
    document: dict,
) -> bool:

    try:

        announcements.insert_one(
            document
        )

        return True

    except DuplicateKeyError:

        return False


def get_announcement(
    nse_id: str,
) -> dict | None:

    return announcements.find_one(
        {
            "nse_id": str(nse_id),
        },
        {
            "_id": 0,
        },
    )


def update_announcement_analysis(
    nse_id: str,
    analysis: dict,
    usage: dict,
) -> None:

    announcements.update_one(
        {
            "nse_id": str(nse_id),
        },
        {
            "$set": {
                "analysis": analysis,
                "ai_usage": usage,
                "analyzed": True,
                "analyzed_at": now_utc(),
            }
        },
    )


def get_recent_announcements(
    symbol: str,
    limit: int = 20,
) -> list[dict]:

    limit = max(
        1,
        min(limit, 100),
    )

    return list(
        announcements.find(
            {
                "symbol": symbol.upper(),
            },
            {
                "_id": 0,
                "raw": 0,
                "filing_text": 0,
            },
        )
        .sort(
            "broadcast_dt",
            DESCENDING,
        )
        .limit(limit)
    )