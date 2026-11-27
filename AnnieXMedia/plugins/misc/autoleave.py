# Authored By Certified Coders © 2025
import asyncio
from datetime import datetime

from pyrogram.enums import ChatType

import config
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController, autoend
from AnnieXMedia.utils.database import get_client, is_active_chat, is_autoend


async def auto_leave():
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(config.AUTO_LEAVE_ASSISTANT_TIME):
            from AnnieXMedia.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if i.chat.id not in (config.LOGGER_ID, -1004478038866):
                                if left >= 20:
                                    break
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except:
                                        continue
                except:
                    pass


try:
    asyncio.create_task(auto_leave())
except RuntimeError:
    pass


async def auto_end():
    while not await asyncio.sleep(5):
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
                except:
                    continue
                try:
                    await app.send_message(
                        chat_id,
                        "» ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇғᴛ ᴠɪᴅᴇᴏᴄʜᴀᴛ ʙᴇᴄᴀᴜsᴇ ɴᴏ ᴏɴᴇ ᴡᴀs ʟɪsᴛᴇɴɪɴɢ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
                    )
                except:
                    continue


try:
    asyncio.create_task(auto_end())
except RuntimeError:
    pass
