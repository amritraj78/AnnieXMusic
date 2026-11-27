# Authored By Certified Coders © 2025
import asyncio
import os
import aiofiles
import aiohttp

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from AnnieXMedia import app
from AnnieXMedia.utils.downloader import get_http_session


async def _stream_file(path: str, chunk_size: int = 65536):
    async with aiofiles.open(path, "rb") as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def _extract_uploaded_url(provider: str, text: str, data: object) -> str:
    if isinstance(data, dict):
        files = data.get("files")
        if isinstance(files, list) and files and isinstance(files[0], dict):
            url = str(files[0].get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
        nested = data.get("data")
        if isinstance(nested, dict):
            url = str(nested.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
    raw = (text or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw
    return ""


async def _post_multipart(session: aiohttp.ClientSession, url: str, field: str, path: str, extra: dict) -> tuple[bool, str]:
    filename = os.path.basename(path) or "upload.bin"
    form = aiohttp.FormData()
    form.add_field(field, _stream_file(path), filename=filename)
    for k, v in extra.items():
        form.add_field(k, v)
    async with session.post(
        url,
        data=form,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AnnieXMusic/1.0)"},
        timeout=aiohttp.ClientTimeout(total=45),
    ) as resp:
        body = await resp.text()
        if resp.status == 200:
            parsed = None
            try:
                parsed = await resp.json(content_type=None)
            except Exception:
                pass
            uploaded_url = _extract_uploaded_url(url, body, parsed)
            if uploaded_url:
                return True, uploaded_url
        return False, f"Error: {resp.status} - {body.strip()[:200]}"


async def upload_file(path: str):
    """Upload file via Catbox with automatic fallback hosts when datacenter IPs are blocked."""
    providers = [
        ("https://catbox.moe/user/api.php", "fileToUpload", {"reqtype": "fileupload"}),
        ("https://qu.ax/upload.php", "files[]", {}),
        ("https://uguu.se/upload", "files[]", {}),
        ("https://tmpfiles.org/api/v1/upload", "file", {}),
    ]
    last_err = "Upload failed."
    session = await get_http_session()

    for url, field, extra in providers:
        try:
            ok, result = await _post_multipart(session, url, field, path, extra)
            if ok:
                return True, result
            last_err = result
        except Exception as exc:
            last_err = str(exc)

    return False, last_err


@app.on_message(filters.command(["tgm", "tgt", "telegraph"]))
async def telegraph_handler(_, message: Message):
    media = message.reply_to_message
    file = (
        (media.photo or media.video or media.document or media.animation)
        if media
        else None
    )
    if not file:
        return await message.reply_text("📎 **Please reply to an image/video/GIF/document to upload.**")

    file_size = getattr(file, "file_size", 0) or 0
    if file_size > 100 * 1024 * 1024:
        return await message.reply_text("⚠️ **File too large. Max size is 100MB.**")

    status = await message.reply("🔄 **Downloading your media...**")

    local_path = None
    try:
        local_path = await media.download()
        if not local_path or not os.path.exists(local_path):
            return await status.edit("❌ **Failed to download media from Telegram.**")

        await status.edit("⬆️ **Uploading media...**")
        success, result = await upload_file(local_path)

        if success:
            await status.edit(
                f"✅ **Uploaded successfully!**\n🔗 [Click to View]({result})",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📎 Open Link", url=result)]]
                ),
            )
        else:
            safe_res = str(result).replace("`", "'")
            await status.edit(f"❌ **Upload failed:**\n`{safe_res}`")

    except Exception as e:
        safe_err = str(e).replace("`", "'")
        await status.edit(f"❌ **Failed to process media:**\n`{safe_err}`")

    finally:
        if local_path and os.path.exists(local_path):
            try:
                await asyncio.to_thread(os.remove, local_path)
            except OSError:
                pass
