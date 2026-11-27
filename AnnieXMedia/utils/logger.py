# Authored By Certified Coders © 2025
import html
from pyrogram.enums import ParseMode

from AnnieXMedia import app
from AnnieXMedia.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype, query: str = None):
    if await is_on_off(2):
        if query is None:
            try:
                query = (message.text or message.caption or "").split(None, 1)[1]
            except Exception:
                query = "—"

        user_id = (
            message.from_user.id
            if message.from_user
            else (message.sender_chat.id if message.sender_chat else 0)
        )
        user_mention = (
            message.from_user.mention
            if message.from_user
            else (html.escape(message.sender_chat.title or "Anonymous") if message.sender_chat else "Anonymous")
        )
        user_username = (
            f"@{html.escape(message.from_user.username)}"
            if message.from_user and message.from_user.username
            else "N/A"
        )
        chat_title = html.escape(message.chat.title or "Private")
        chat_username = f"@{html.escape(message.chat.username)}" if message.chat.username else "Private"

        logger_text = f"""
<b>{app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{message.chat.id}</code>
<b>ᴄʜᴀᴛ ɴᴀᴍᴇ :</b> {chat_title}
<b>ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ :</b> {chat_username}

<b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>
<b>ɴᴀᴍᴇ :</b> {user_mention}
<b>ᴜsᴇʀɴᴀᴍᴇ :</b> {user_username}

<b>ǫᴜᴇʀʏ :</b> {html.escape(str(query)[:500])}
<b>sᴛʀᴇᴀᴍᴛʏᴘᴇ :</b> {html.escape(str(streamtype))}"""
        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return
