# Authored By Certified Coders © 2025
import asyncio
import os
import aiohttp
import aiofiles

from config import DEEP_API
from AnnieXMedia import app
from AnnieXMedia.utils.downloader import get_http_session
from AnnieXMedia.utils.security import fetch_url_limited, redact_secrets
from pyrogram import filters
from pyrogram.types import Message

_MAX_IMAGE_BYTES = 25 * 1024 * 1024


async def download_from_url(path: str, url: str) -> str | None:
    ok, status, _, data = await fetch_url_limited(
        url,
        max_bytes=_MAX_IMAGE_BYTES,
        max_redirects=3,
        timeout=30.0,
    )
    if not ok or status != 200 or not data:
        return None
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    async with aiofiles.open(path, mode="wb") as f:
        await f.write(data)
    return path


async def post_file(url: str, file_path: str, headers: dict):
    async with aiofiles.open(file_path, "rb") as f:
        raw = await f.read(_MAX_IMAGE_BYTES + 1)
    if len(raw) > _MAX_IMAGE_BYTES:
        return {"err": "File exceeds 25 MB limit."}
    form = aiohttp.FormData()
    form.add_field("image", raw, filename=os.path.basename(file_path), content_type="application/octet-stream")
    session = await get_http_session()
    async with session.post(url, data=form, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            return None
        return await resp.json(content_type=None)


async def post_data(url: str, data: dict, headers: dict):
    session = await get_http_session()
    async with session.post(url, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            return None
        return await resp.json(content_type=None)


@app.on_message(filters.command("upscale"))
async def upscale_image(_, message: Message):
    if not DEEP_API:
        return await message.reply_text("🚫 Missing DeepAI API key.")

    reply = message.reply_to_message
    if not reply or not reply.photo:
        return await message.reply_text("📎 Please reply to an image.")

    status = await message.reply_text("🔄 Upscaling image...")
    local_path = None
    try:
        local_path = await reply.download()
        if not local_path or not os.path.exists(local_path):
            return await status.edit("❌ Failed to download image.")
        resp = await post_file(
            "https://api.deepai.org/api/torch-srgan",
            local_path,
            headers={'api-key': DEEP_API}
        )

        image_url = resp.get("output_url") if isinstance(resp, dict) else None
        if not image_url:
            return await status.edit("❌ Upscale request failed.")

        final_path = await download_from_url(local_path, image_url)
        if not final_path:
            return await status.edit("❌ Could not download result.")

        try:
            await status.delete()
        except Exception:
            pass
        await message.reply_document(final_path)

    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        await status.edit(f"⚠️ Error: `{safe_err}`")
    finally:
        if local_path and os.path.exists(local_path):
            try:
                await asyncio.to_thread(os.remove, local_path)
            except OSError:
                pass


@app.on_message(filters.command("getdraw"))
async def draw_image(_, message: Message):
    if not DEEP_API:
        return await message.reply_text("🚫 DeepAI API key is missing.")

    reply = message.reply_to_message
    query = None

    if reply and (reply.text or reply.caption):
        query = reply.text or reply.caption
    elif len(message.command) > 1:
        query = message.text.split(None, 1)[1]

    if not query:
        return await message.reply_text("💬 Please reply or provide text.")

    status = await message.reply_text("🎨 Generating image...")

    user_id = message.from_user.id if message.from_user else message.chat.id
    chat_id = message.chat.id
    temp_path = f"cache/{user_id}_{chat_id}_{message.id}.png"

    try:
        resp = await post_data(
            "https://api.deepai.org/api/text2img",
            data={'text': query, 'grid_size': '1', 'image_generator_version': 'hd'},
            headers={'api-key': DEEP_API}
        )

        image_url = resp.get("output_url") if isinstance(resp, dict) else None
        if not image_url:
            return await status.edit("❌ Failed to generate image.")

        final_path = await download_from_url(temp_path, image_url)
        if not final_path:
            return await status.edit("❌ Error downloading image.")

        try:
            await status.delete()
        except Exception:
            pass
        safe_q = query[:900].replace("`", "'")
        safe_cap = f"`{safe_q}`"
        try:
            await message.reply_photo(final_path, caption=safe_cap)
        except Exception:
            await message.reply_document(final_path, caption=safe_cap)

    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        await status.edit(f"⚠️ Error: `{safe_err}`")
    finally:
        if os.path.exists(temp_path):
            try:
                await asyncio.to_thread(os.remove, temp_path)
            except OSError:
                pass
