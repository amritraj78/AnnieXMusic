# Authored By Certified Coders © 2025
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.logging import LOGGER

TRUTH_API = "https://api.truthordarebot.xyz/v1/truth"
DARE_API = "https://api.truthordarebot.xyz/v1/dare"


@app.on_message(filters.command("truth"))
async def get_truth(client: Client, message: Message):
    try:
        http = await get_http_session()
        async with http.get(TRUTH_API, timeout=aiohttp.ClientTimeout(total=10)) as res:
            if res.status == 200:
                data = await res.json(content_type=None)
                question = str((data or {}).get("question") or "No question found.").replace("`", "'")
                await message.reply_text(
                    f"🔎 **Truth:**\n\n{question}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.reply_text("❌ Failed to fetch a truth question.")
    except Exception as e:
        LOGGER(__name__).debug(f"Truth error: {e}")
        await message.reply_text("⚠️ Error occurred while fetching a truth question.")


@app.on_message(filters.command("dare"))
async def get_dare(client: Client, message: Message):
    try:
        http = await get_http_session()
        async with http.get(DARE_API, timeout=aiohttp.ClientTimeout(total=10)) as res:
            if res.status == 200:
                data = await res.json(content_type=None)
                question = str((data or {}).get("question") or "No question found.").replace("`", "'")
                await message.reply_text(
                    f"🎯 **Dare:**\n\n{question}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.reply_text("❌ Failed to fetch a dare question.")
    except Exception as e:
        LOGGER(__name__).debug(f"Dare error: {e}")
        await message.reply_text("⚠️ Error occurred while fetching a dare question.")
