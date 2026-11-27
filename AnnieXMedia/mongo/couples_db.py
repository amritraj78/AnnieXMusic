# Authored By Certified Coders © 2025
from typing import Any, Dict
from AnnieXMedia.core.mongo import mongodb

coupledb = mongodb["couple"]
_MAX_DATES_PER_CHAT = 30


async def _doc(cid: int) -> dict:
    return await coupledb.find_one({"chat_id": cid}) or {}


async def get_couple(cid: int, date: str):
    doc = await _doc(cid)
    couple_map = doc.get("couple")
    if not isinstance(couple_map, dict):
        return None
    entry = couple_map.get(date)
    if not isinstance(entry, dict) or "user1" not in entry or "user2" not in entry:
        return None

    img_field = doc.get("img")
    img_path = img_field.get(date) if isinstance(img_field, dict) else img_field

    return {
        "user1": entry["user1"],
        "user2": entry["user2"],
        "img": img_path,
    }


async def save_couple(cid: int, date: str, couple: dict, img_path: str):
    doc = await _doc(cid)
    couple_map: Dict[str, Any] = dict(doc["couple"]) if isinstance(doc.get("couple"), dict) else {}
    img_field: Dict[str, Any] = dict(doc["img"]) if isinstance(doc.get("img"), dict) else {}

    couple_map[date] = couple
    img_field[date] = img_path

    if len(couple_map) > _MAX_DATES_PER_CHAT:
        keep_keys = list(couple_map.keys())[-_MAX_DATES_PER_CHAT:]
        couple_map = {k: couple_map[k] for k in keep_keys}
        img_field = {k: img_field[k] for k in keep_keys if k in img_field}

    await coupledb.update_one(
        {"chat_id": cid},
        {"$set": {"couple": couple_map, "img": img_field}},
        upsert=True,
    )
