# Authored By Certified Coders © 2025
import asyncio
from datetime import datetime
from typing import Optional

from pyrogram.enums import ChatType

import config
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController, autoend
from AnnieXMedia.utils.database import get_client, is_active_chat, is_autoend

_leave_task: Optional[asyncio.Task] = None
_end_task: Optional[asyncio.Task] = None


async def auto_leave():
    if not config.AUTO_LEAVING_ASSISTANT:
        return
    while not await asyncio.sleep(config.AUTO_LEAVE_ASSISTANT_TIME):
        try:
            from AnnieXMedia.core.userbot import assistants

            for num in list(assistants):
                client = await get_client(num)
                if not client:
                    continue
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in (
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ):
                            if i.chat.id not in (config.LOGGER_ID, -1004478038866):
                                if left >= 20:
                                    break
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except Exception:
                                        continue
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass


async def auto_end():
    while not await asyncio.sleep(5):
        try:
            ender = await is_autoend()
            if not ender:
                continue
            for chat_id in list(autoend.keys()):
                timer = autoend.get(chat_id)
                if not timer or not isinstance(timer, datetime):
                    autoend.pop(chat_id, None)
                    continue
                if datetime.now() > timer:
                    autoend.pop(chat_id, None)
                    if not await is_active_chat(chat_id):
                        continue
                    try:
                        await StreamController.stop_stream(chat_id)
                    except Exception:
                        continue
                    try:
                        await app.send_message(
                            chat_id,
                            "» ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇғᴛ ᴠɪᴅᴇᴏᴄʜᴀᴛ ʙᴇᴄᴀᴜsᴇ ɴᴏ ᴏɴᴇ ᴡᴀs ʟɪsᴛᴇɴɪɴɢ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
                        )
                    except Exception:
                        continue
        except asyncio.CancelledError:
            raise
        except Exception:
            continue


def ensure_autoleave_tasks() -> bool:
    """Start or restart autoleave/autoend background tasks if stopped. Return True if restarted."""
    global _leave_task, _end_task
    started = False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    if config.AUTO_LEAVING_ASSISTANT and (_leave_task is None or _leave_task.done()):
        _leave_task = loop.create_task(auto_leave(), name="auto-leave")
        started = True
    if _end_task is None or _end_task.done():
        _end_task = loop.create_task(auto_end(), name="auto-end")
        started = True
    return started


ensure_autoleave_tasks()
