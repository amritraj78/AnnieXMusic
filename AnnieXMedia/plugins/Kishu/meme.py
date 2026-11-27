# Authored By Certified Coders © 2025
import html
import re
import aiohttp
from pyrogram import Client, filters
from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.logging import LOGGER


@app.on_message(filters.command("meme"))
async def meme_command(client, message):
    args = message.text.split()
    category = args[1].strip() if len(args) > 1 else ""
    if category and not re.match(r"^[A-Za-z0-9_]{1,50}$", category):
        return await message.reply_text("❌ Invalid subreddit/category name.")

    api_url = f"https://meme-api.com/gimme/{category}" if category else "https://meme-api.com/gimme"

    try:
        http_client = await get_http_session()
        async with http_client.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            try:
                data = await response.json(content_type=None)
            except Exception:
                data = {}
            status = response.status

        if status == 403 or ("message" in data and "Unable to Access Subreddit" in str(data.get("message"))):
            return await message.reply_text("❌ Memes from this category are not found. Please try a different one.")

        meme_url = data.get("url")
        title = html.escape(str(data.get("title") or "Meme"))

        if not meme_url:
            return await message.reply_text("❌ Couldn't find a meme image. Please try again.")

        user_mention = message.from_user.mention if message.from_user else "User"

        caption = (
            f"{title}\n\n"
            f"Request by {user_mention}\n"
            f"Bot username: @{app.username}"
        )

        try:
            await message.reply_photo(photo=meme_url, caption=caption[:1024])
        except Exception:
            await message.reply_text(f"{caption}\n\n{meme_url}"[:4096])

    except Exception as e:
        LOGGER(__name__).debug(f"Error fetching meme: {e}")
        await message.reply_text("Sorry, I couldn't fetch a meme at the moment.")
