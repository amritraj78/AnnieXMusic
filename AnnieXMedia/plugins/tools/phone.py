# Authored By Certified Coders © 2025
import os
import re
import aiohttp
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.utils.downloader import get_http_session
from AnnieXMedia.utils.security import redact_secrets

API_KEY = os.getenv("NUMVERIFY_API_KEY", "f66950368a61ebad3cba9b5924b4532d")
API_URL = "http://apilayer.net/api/validate"


def _clean_md(v: object) -> str:
    return str(v or "N/A").replace("`", "'")


@app.on_message(filters.command("phone"))
async def check_phone(_, message: Message):

    if len(message.command) < 2:
        return await message.reply_text(
            "📱 **ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ.**\n"
            "**ᴜꜱᴀɢᴇ:** `/phone <number>`",
            parse_mode=ParseMode.MARKDOWN
        )

    number = message.command[1].strip()
    if not re.match(r"^\+?[0-9\-\s()]{4,24}$", number):
        return await message.reply_text(
            "❌ **ɪɴᴠᴀʟɪᴅ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ ꜰᴏʀᴍᴀᴛ.**",
            parse_mode=ParseMode.MARKDOWN
        )

    params = {
        "access_key": API_KEY,
        "number": number,
        "country_code": "",
        "format": 1
    }

    try:
        session = await get_http_session()
        async with session.get(
            API_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status != 200:
                return await message.reply_text(
                    "❌ **ɴᴇᴛᴡᴏʀᴋ ᴇʀʀᴏʀ. ᴀᴘɪ ɴᴏᴛ ʀᴇᴀᴄʜᴀʙʟᴇ.**",
                    parse_mode=ParseMode.MARKDOWN
                )

            try:
                data = await response.json()
            except Exception:
                return await message.reply_text(
                    "❌ **Invalid response from API service.**",
                    parse_mode=ParseMode.MARKDOWN
                )

            if not data or not data.get("valid"):
                return await message.reply_text(
                    "❌ **ɪɴᴠᴀʟɪᴅ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ.**",
                    parse_mode=ParseMode.MARKDOWN
                )

            result = (
                "📞 **ᴠᴀʟɪᴅ ᴘʜᴏɴᴇ ᴅᴇᴛᴀɪʟꜱ:**\n"
                f"➤ **ɴᴜᴍʙᴇʀ:** `{_clean_md(number)}`\n"
                f"➤ **ᴄᴏᴜɴᴛʀʏ:** `{_clean_md(data.get('country_name'))} ({_clean_md(data.get('country_code'))})`\n"
                f"➤ **ʟᴏᴄᴀᴛɪᴏɴ:** `{_clean_md(data.get('location'))}`\n"
                f"➤ **ᴄᴀʀʀɪᴇʀ:** `{_clean_md(data.get('carrier'))}`\n"
                f"➤ **ᴅᴇᴠɪᴄᴇ ᴛʏᴘᴇ:** `{_clean_md(data.get('line_type'))}`"
            )

            return await message.reply_text(result, parse_mode=ParseMode.MARKDOWN)

    except aiohttp.ClientError as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        return await message.reply_text(
            f"⚠️ **ɴᴇᴛᴡᴏʀᴋ ᴇʀʀᴏʀ:** `{safe_err}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        return await message.reply_text(
            f"⚠️ **ᴜɴᴋɴᴏᴡɴ ᴇʀʀᴏʀ:** `{safe_err}`",
            parse_mode=ParseMode.MARKDOWN
        )
