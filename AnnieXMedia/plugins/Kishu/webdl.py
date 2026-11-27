# Authored By Certified Coders © 2025
import asyncio
import os
import socket
import ipaddress
from urllib.parse import urljoin, urlparse
import httpx
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from AnnieXMedia import app

MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB limit for 512MB RAM container safety


def _is_ip_restricted(ip_obj) -> bool:
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def _is_safe_url_sync(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        if host.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
            return False
        infos = socket.getaddrinfo(host, None)
        if not infos:
            return False
        for _, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0].split("%", 1)[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if _is_ip_restricted(ip_obj):
                return False
        return True
    except Exception:
        return False


async def is_safe_url(url: str) -> bool:
    return await asyncio.to_thread(_is_safe_url_sync, url)


async def download_website(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    current_url = url
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            for _ in range(5):
                if not await is_safe_url(current_url):
                    return "❌ Invalid or restricted URL (internal/private addresses cannot be accessed)."
                response = await client.get(current_url, headers=headers)
                if response.is_redirect and "location" in response.headers:
                    current_url = urljoin(current_url, response.headers["location"])
                    continue
                if response.status_code == 200:
                    if len(response.content) > MAX_BODY_BYTES:
                        return "❌ Website response exceeds 5 MB safety limit."
                    return response.text
                return f"❌ Failed to download source code. Status code: {response.status_code}"
            return "❌ Too many redirects."
    except Exception as e:
        return f"❌ An error occurred: {str(e)}"


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
        return await status_msg.edit_text(source_code, parse_mode=enums.ParseMode.MARKDOWN)

    os.makedirs("cache", exist_ok=True)
    file_path = f"cache/webdl_{message.chat.id}_{message.id}.txt"
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(source_code)

        await message.reply_document(
            document=file_path,
            caption=f"📄 Source code of: `{url}`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except Exception as e:
        await message.reply_text(
            f"❌ Failed to send the file: `{e}`",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    try:
        await status_msg.delete()
    except Exception:
        pass
