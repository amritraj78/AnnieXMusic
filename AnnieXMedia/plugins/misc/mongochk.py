# Authored By Certified Coders © 2025
import asyncio
import re
from urllib.parse import parse_qsl, urlsplit
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from pymongo import MongoClient

from AnnieXMedia import app
from AnnieXMedia.utils.security import _resolve_safe_host, redact_secrets

mongo_url_pattern = re.compile(r"^mongodb(?:\+srv)?://[^\s]+$")
_MONGO_SEM = asyncio.Semaphore(3)
_FORBIDDEN_MONGO_PARAMS = {
    "tlscafile",
    "tlscertificatekeyfile",
    "tlscrlfile",
    "ssl_ca_certs",
    "ssl_certfile",
    "ssl_keyfile",
    "ssl_crlfile",
    "authmechanismproperties",
}


async def _is_safe_mongo_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(url)
    except Exception:
        return False, "Invalid MongoDB URI."

    if parsed.scheme not in ("mongodb", "mongodb+srv"):
        return False, "Unsupported URI scheme."

    # Reject local unix-domain socket references or forbidden file-reading TLS params
    raw_authority = parsed.netloc.rsplit("@", 1)[-1]
    if not raw_authority or "%2f" in raw_authority.lower() or "/" in raw_authority:
        return False, "Invalid host specification."

    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _FORBIDDEN_MONGO_PARAMS:
            return False, f"Forbidden query option: {key}"

    hosts = [h.strip() for h in raw_authority.split(",") if h.strip()]
    if not hosts:
        return False, "No MongoDB host provided."

    for host_port in hosts:
        # Handle IPv6 [addr]:port or host:port
        if host_port.startswith("["):
            host = host_port[1:].split("]", 1)[0]
        else:
            host = host_port.split(":", 1)[0]
        ips = await _resolve_safe_host(host)
        if not ips:
            return False, "Internal, private, or unresolvable MongoDB host is blocked."

    return True, ""


def _test_mongo_sync(url: str):
    client = MongoClient(url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000)
    try:
        client.server_info()
    finally:
        client.close()


@app.on_message(filters.command("mongochk"))
async def mongo_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ **Usage:** `/mongochk <your_mongodb_url>`",
            parse_mode=ParseMode.MARKDOWN
        )

    mongo_url = message.command[1].strip()

    if not re.match(mongo_url_pattern, mongo_url):
        return await message.reply_text(
            "❌ **Invalid MongoDB URL format.**\nIt should start with `mongodb://` or `mongodb+srv://`.",
            parse_mode=ParseMode.MARKDOWN
        )

    safe, reason = await _is_safe_mongo_url(mongo_url)
    if not safe:
        return await message.reply_text(
            f"❌ **Rejected:** {reason}",
            parse_mode=ParseMode.MARKDOWN
        )

    try:
        async with _MONGO_SEM:
            await asyncio.to_thread(_test_mongo_sync, mongo_url)
        await message.reply_text(
            "✅ **MongoDB URL is valid and connection was successful.**",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        await message.reply_text(
            f"❌ **Failed to connect to MongoDB:**\n`{safe_err}`",
            parse_mode=ParseMode.MARKDOWN
        )
