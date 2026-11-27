# Authored By Certified Coders © 2025
import asyncio
import os
import aiofiles
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.utils.security import fetch_url_limited, redact_secrets

MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB limit for 512MB RAM container safety


async def download_website(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        ok, status_code, final_or_err, body = await fetch_url_limited(
            url,
            max_bytes=MAX_BODY_BYTES,
            max_redirects=5,
            timeout=15.0,
            headers=headers,
        )
        if not ok:
            msg = redact_secrets(final_or_err or "Request rejected.")
            return f"❌ {msg}"
        if status_code != 200:
            return f"❌ Failed to download source code. Status code: {status_code}"
        return body.decode("utf-8", errors="replace")
    except Exception as e:
        return f"❌ An error occurred: {redact_secrets(str(e))}"


@app.on_message(filters.command("webdl"))
async def web_download(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please enter a valid URL.\n\nExample: `/webdl https://example.com`",
            parse_mode=enums.ParseMode.MARKDOWN
        )

    url = message.command[1].strip()
    status_msg = await message.reply_text("⏳ Downloading website source...")

    source_code = await download_website(url)

    if source_code.startswith("❌"):
        return await status_msg.edit_text(source_code.replace("`", "'"), parse_mode=enums.ParseMode.MARKDOWN)

    os.makedirs("cache", exist_ok=True)
    file_path = f"cache/webdl_{message.chat.id}_{message.id}.txt"
    try:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(source_code)

        safe_url = url.replace("`", "'")
        await message.reply_document(
            document=file_path,
            caption=f"📄 Source code of: `{safe_url}`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        await message.reply_text(
            f"❌ Failed to send the file: `{safe_err}`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    finally:
        if os.path.exists(file_path):
            try:
                await asyncio.to_thread(os.remove, file_path)
            except Exception:
                pass

    try:
        await status_msg.delete()
    except Exception:
        pass
