# Authored By Certified Coders © 2025
import asyncio
import os
import uuid
import aiofiles
import aiohttp
from pyrogram import filters
from AnnieXMedia import app
from AnnieXMedia.utils.downloader import get_http_session

API_KEY = os.getenv("REMOVE_BG_API_KEY", "23nfCEipDijgVv6SH14oktJe")
_MAX_IMAGE_BYTES = 20 * 1024 * 1024


async def remove_background(image_path: str) -> tuple:
    headers = {"X-API-Key": API_KEY}
    try:
        async with aiofiles.open(image_path, "rb") as img:
            raw_bytes = await img.read(_MAX_IMAGE_BYTES + 1)
        if len(raw_bytes) > _MAX_IMAGE_BYTES:
            return False, {"title": "File Too Large", "errors": [{"detail": "Image exceeds 20 MB limit."}]}

        form = aiohttp.FormData()
        form.add_field("image_file", raw_bytes, filename=os.path.basename(image_path))

        session = await get_http_session()
        async with session.post(
            "https://api.remove.bg/v1.0/removebg",
            headers=headers,
            data=form,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if "image" not in response.headers.get("content-type", ""):
                try:
                    return False, await response.json()
                except Exception:
                    return False, {"title": f"HTTP {response.status}", "errors": [{"detail": "Unexpected response"}]}

            body = await response.read()
            if len(body) > _MAX_IMAGE_BYTES:
                return False, {"title": "Output Too Large", "errors": [{"detail": "Result exceeds 20 MB."}]}

            os.makedirs("downloads", exist_ok=True)
            output_filename = f"downloads/no_bg_{uuid.uuid4().hex[:8]}.png"
            async with aiofiles.open(output_filename, "wb") as out_file:
                await out_file.write(body)
            return True, output_filename

    except Exception as e:
        return False, {"title": "Unknown Error", "errors": [{"detail": str(e)}]}


@app.on_message(filters.command("rmbg"))
async def remove_bg_command(client, message):
    status = await message.reply("🖌️ Processing your image...")
    replied = message.reply_to_message

    if not replied or not replied.photo:
        return await status.edit("Please reply to a photo to remove its background.")

    downloaded_photo = None
    result = None
    try:
        downloaded_photo = await client.download_media(replied)
        if not downloaded_photo:
            return await status.edit("❌ Failed to download the image.")
        success, result = await remove_background(downloaded_photo)

        if not success:
            title = result.get("title", "Error") if isinstance(result, dict) else "Error"
            errors = result.get("errors", [{}]) if isinstance(result, dict) else [{}]
            detail = errors[0].get("detail", str(result)) if errors else str(result)
            return await status.edit(f"⚠️ ERROR: {title}\n{detail}")

        await message.reply_photo(photo=result, caption="✅ Here's your image without background.")
        await message.reply_document(document=result)
        try:
            await status.delete()
        except Exception:
            pass

    except Exception as e:
        await status.edit(f"❌ Failed to process the image.\nError: {e}")
    finally:
        for p in (downloaded_photo, result):
            if p and isinstance(p, str) and os.path.exists(p):
                try:
                    await asyncio.to_thread(os.remove, p)
                except Exception:
                    pass
