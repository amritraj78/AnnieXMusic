# Authored By Certified Coders © 2025
from datetime import datetime, timedelta, timezone
from typing import Optional
from pymongo import ReturnDocument

from AnnieXMedia.core.mongo import mongodb

_col = mongodb["welcome"]


async def is_on(chat_id: int) -> bool:
    doc = await _col.find_one({"_id": chat_id}, {"state": 1})
    return (doc or {}).get("state", "on") == "on"


async def set_state(chat_id: int, flag: str) -> None:
    if flag not in ("on", "off"):
        raise ValueError("flag must be 'on' or 'off'")
    await _col.update_one({"_id": chat_id}, {"$set": {"state": flag}}, upsert=True)


async def bump(chat_id: int, time_window: int = 8) -> int:
    """Atomically increment burst join counter inside window, avoiding raid-count race conditions."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=time_window)

    # First try atomic increment if last_ts is within active window
    updated = await _col.find_one_and_update(
        {"_id": chat_id, "last_ts": {"$gte": cutoff}},
        {"$inc": {"join_cnt": 1}, "$set": {"last_ts": now}},
        return_document=ReturnDocument.AFTER,
    )
    if updated and "join_cnt" in updated:
        return int(updated["join_cnt"])

    # Window expired or first doc: atomically reset counter to 1
    doc = await _col.find_one_and_update(
        {"_id": chat_id},
        {"$set": {"last_ts": now, "join_cnt": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int((doc or {}).get("join_cnt") or 1)


async def cool(chat_id: int, cool_minutes: int = 10) -> None:
    now = datetime.now(timezone.utc)
    await _col.update_one(
        {"_id": chat_id},
        {
            "$set": {
                "state": "off",
                "cool_until": now + timedelta(minutes=cool_minutes),
            }
        },
        upsert=True,
    )


async def auto_on(chat_id: int) -> bool:
    """Atomically re-enable welcome once cooldown expires, returning True at most once."""
    now = datetime.now(timezone.utc)
    prev = await _col.find_one_and_update(
        {"_id": chat_id, "cool_until": {"$lte": now}},
        {"$set": {"state": "on"}, "$unset": {"cool_until": ""}},
        return_document=ReturnDocument.BEFORE,
    )
    return bool(prev)
