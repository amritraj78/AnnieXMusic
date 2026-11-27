# Authored By Certified Coders © 2025
import asyncio
import sys
from typing import Dict, List, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI
from ..logging import LOGGER

LOGGER(__name__).info("Connecting to your Mongo Database...")

if not MONGO_DB_URI or not str(MONGO_DB_URI).strip():
    LOGGER(__name__).error("MONGO_DB_URI is missing! Set MONGO_DB_URI in environment variables.")
    sys.exit(1)

try:
    _mongo_async_ = AsyncIOMotorClient(
        MONGO_DB_URI,
        serverSelectionTimeoutMS=12500,
        connectTimeoutMS=10000,
        maxPoolSize=20,
        minPoolSize=1,
    )
    mongodb = _mongo_async_.Annie
    LOGGER(__name__).info("Connected to your Mongo Database.")
except Exception as e:
    LOGGER(__name__).error(f"Failed to connect to your Mongo Database: {e}")
    sys.exit(1)


_CHAT_ID_COLLECTIONS = (
    "chats",
    "language",
    "assistants",
    "adminauth",
    "authuser",
    "playmode",
    "playtypedb",
    "skipmode",
    "upcount",
    "cplaymode",
    "blacklistChat",
    "autoend",
    "couple",
)
_USER_ID_COLLECTIONS = ("tgusersdb", "gban", "blockedusers")
_EXTRA_INDEXES: Dict[str, List[List[Tuple[str, int]]]] = {
    "game_scores": [
        [("game", 1), ("score", -1), ("updated_at", 1)],
        [("user_id", 1), ("game", 1)],
    ],
    "onoffper": [[("on_off", 1)]],
    "pretender": [
        [("user_id", 1)],
        [("chat_id_toggle", 1)],
    ],
}


async def ensure_indexes() -> None:
    """Create MongoDB indexes for fast lookups and Mini App leaderboards."""
    tasks = []
    for name in _CHAT_ID_COLLECTIONS:
        tasks.append(mongodb[name].create_index([("chat_id", 1)], background=True))
    for name in _USER_ID_COLLECTIONS:
        tasks.append(mongodb[name].create_index([("user_id", 1)], background=True))
    for name, specs in _EXTRA_INDEXES.items():
        for spec in specs:
            tasks.append(mongodb[name].create_index(spec, background=True))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        LOGGER(__name__).warning(f"MongoDB index setup completed with {len(failures)} warning(s): {failures[0]}")
    else:
        LOGGER(__name__).info(f"MongoDB indexes verified ({len(tasks)} indexes).")
