# Authored By Certified Coders © 2025
from datetime import datetime
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from config import BOT_USERNAME
from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session


@app.on_message(filters.command("write"))
async def handwrite(_, message: Message):
    replied_txt = (message.reply_to_message.text or message.reply_to_message.caption) if message.reply_to_message else None
    if replied_txt:
        text = replied_txt
    elif len(message.command) > 1:
        parts = (message.text or message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply_text("❌ Please provide some text to write.")
        text = parts[1]
    else:
        return await message.reply_text(
            "❌ Please provide some text to write.\n\nUse `/write your message` or reply to a message.",
            parse_mode=enums.ParseMode.MARKDOWN
        )

    text = text[:500]
    msg = await message.reply_text("✍️ Please wait...\nWriting your text...")

    try:
        client = await get_http_session()
        async with client.get(
            "https://apis.xditya.me/write",
            params={"text": text},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status != 200:
                raise Exception(f"API Error {response.status}")
            image_url = str(response.url)
    except Exception:
        return await msg.edit(
            "❌ Failed to generate handwritten text. Try again later.",
            parse_mode=enums.ParseMode.MARKDOWN
        )

    user_mention = message.from_user.mention if message.from_user else "User"
    caption = (
        f"📝 𝒮𝓊𝒸𝒸𝑒𝓈𝓈!\n\n"
        f"✨ 𝒲𝓇𝒾𝓉𝓉𝑒𝓃 𝒷𝓎: [𝐀𝐍𝐍𝐈𝐄](https://t.me/{app.username or BOT_USERNAME})\n"
        f"🥀 𝑅𝑒𝓆𝓊𝑒𝓈𝓉𝑒𝒹 𝒷𝓎: {user_mention}"
    )

    try:
        await msg.delete()
    except Exception:
        pass

    try:
        await message.reply_photo(photo=image_url, caption=caption)
    except Exception:
        await message.reply_text(f"{caption}\n\n{image_url}")


@app.on_message(filters.command("day"))
async def date_to_day_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide a date in this format: `/day 1947-08-15`",
            parse_mode=enums.ParseMode.MARKDOWN
        )

    input_date = message.command[1].strip()
    try:
        date_object = datetime.strptime(input_date, "%Y-%m-%d")
        day_of_week = date_object.strftime("%A")

        await message.reply_text(
            f"📆 The day of the week for `{input_date}` is **{day_of_week}**.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except ValueError:
        await message.reply_text(
            "❌ Invalid date format. Please use: `/day YYYY-MM-DD`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
