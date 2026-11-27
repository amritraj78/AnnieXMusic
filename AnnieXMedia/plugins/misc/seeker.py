# Authored By Certified Coders © 2025
import asyncio

from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import get_active_chats, is_music_playing


async def timer():
    while not await asyncio.sleep(1):
        try:
            active_chats = await get_active_chats()
            for chat_id in active_chats:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing or not isinstance(playing, list) or not playing[0]:
                    continue
                try:
                    duration = int(playing[0].get("seconds", 0))
                except (ValueError, TypeError):
                    continue
                if duration == 0:
                    continue
                if playing[0].get("played", 0) >= duration:
                    continue
                playing[0]["played"] = playing[0].get("played", 0) + 1
        except Exception:
            continue


try:
    asyncio.create_task(timer())
except RuntimeError:
    pass
