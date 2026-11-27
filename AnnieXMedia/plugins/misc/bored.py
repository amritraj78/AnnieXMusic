# Authored By Certified Coders © 2025
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.logging import LOGGER

BORED_API_URL = "https://apis.scrimba.com/bored/api/activity"


@app.on_message(filters.command("bored"))
async def bored_command(client: Client, message: Message):
    try:
        http = await get_http_session()
        async with http.get(BORED_API_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return await message.reply_text(
                    "❌ Failed to fetch a fun activity. Try again later.",
                )
            data = await response.json(content_type=None)

        activity = data.get("activity") if isinstance(data, dict) else None

        if activity:
            safe_act = str(activity).replace("`", "'")
            await message.reply_text(
                f"😐 **Feeling bored?**\n\n🎯 **Try this:** `{safe_act}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.reply_text("🤷 No activity found.")

    except Exception as e:
        LOGGER(__name__).debug(f"Bored API error: {e}")
        await message.reply_text(
            "⚠️ Something went wrong while fetching boredom busters.",
        )
