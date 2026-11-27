# Authored By Certified Coders © 2025
import asyncio
import ipaddress
import json
import socket
from datetime import datetime, timezone
import whois
from pyrogram import filters

from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.security import fetch_url_limited


async def get_domain_info(domain_name):
    try:
        return await asyncio.to_thread(whois.whois, domain_name)
    except Exception as e:
        LOGGER(__name__).debug(f"[WHOIS Error] {e}")
        return None


def get_domain_age(creation_date):
    if isinstance(creation_date, list):
        creation_date = creation_date[0] if creation_date else None
    if not creation_date or not isinstance(creation_date, datetime):
        return None
    now = datetime.now(timezone.utc) if creation_date.tzinfo else datetime.now()
    try:
        return (now - creation_date).days // 365
    except Exception:
        return None


async def get_ip_location(ip: str):
    try:
        addr = ipaddress.ip_address(ip)
        if not addr.is_global:
            return None
        ok, status, _, body = await fetch_url_limited(
            f"https://ipwho.is/{addr}",
            max_bytes=64 * 1024,
            max_redirects=2,
            timeout=8.0,
        )
        if ok and status == 200 and body:
            data = json.loads(body.decode("utf-8", errors="replace"))
            if data.get("success"):
                return data
    except Exception as e:
        LOGGER(__name__).debug(f"[IP Geo Error] {e}")
    return None


def _clean_md(val) -> str:
    if not val:
        return "N/A"
    return str(val).replace("`", "'").replace("[", "(").replace("]", ")")


async def format_info(info, fallback_domain: str):
    def clean(item):
        if isinstance(item, list):
            return item[0] if item else None
        return item

    domain = clean(getattr(info, "domain_name", None)) or fallback_domain
    registrar = clean(getattr(info, "registrar", None))
    creation = clean(getattr(info, "creation_date", None))
    expiry = clean(getattr(info, "expiration_date", None))
    ns_raw = getattr(info, "name_servers", None)
    if isinstance(ns_raw, (list, set, tuple)):
        nameservers = ", ".join(str(x) for x in sorted(ns_raw, key=str)) or "N/A"
    elif ns_raw:
        nameservers = str(ns_raw)
    else:
        nameservers = "N/A"
    age = get_domain_age(creation)

    try:
        ip = await asyncio.to_thread(socket.gethostbyname, str(domain))
    except Exception:
        ip = "Unavailable"

    location_data = await get_ip_location(ip) if ip != "Unavailable" else None
    if location_data:
        location = f"{location_data.get('country', 'Unknown')}, {location_data.get('city', 'Unknown')}"
    else:
        location = "Unavailable"

    return (
        f"**ᴅᴏᴍᴀɪɴ ɴᴀᴍᴇ**: `{_clean_md(domain)}`\n"
        f"**ʀᴇɢɪsᴛʀᴀʀ**: {_clean_md(registrar)}\n"
        f"**ᴄʀᴇᴀᴛɪᴏɴ ᴅᴀᴛᴇ**: {creation.strftime('%Y-%m-%d') if hasattr(creation, 'strftime') else (creation or 'N/A')}\n"
        f"**ᴇxᴘɪʀᴀᴛɪᴏɴ ᴅᴀᴛᴇ**: {expiry.strftime('%Y-%m-%d') if hasattr(expiry, 'strftime') else (expiry or 'N/A')}\n"
        f"**ᴅᴏᴍᴀɪɴ ᴀɢᴇ**: {age if age is not None else 'N/A'} years\n"
        f"**ɪᴘ ᴀᴅᴅʀᴇss**: `{_clean_md(ip)}`\n"
        f"**ʟᴏᴄᴀᴛɪᴏɴ**: {_clean_md(location)}\n"
        f"**ɴᴀᴍᴇsᴇʀᴠᴇʀs**: {_clean_md(nameservers)}\n"
    )


@app.on_message(filters.command("domain"))
async def domain_lookup(_, message):
    if len(message.command) < 2:
        return await message.reply("Please provide a domain name. Example: `/domain heroku.com`")

    parts = (message.text or message.caption or "").split(maxsplit=1)
    domain_name = parts[1].strip() if len(parts) > 1 else ""
    if len(domain_name) > 253 or " " in domain_name:
        return await message.reply("⚠️ Please provide a valid domain name.")
    status = await message.reply("🔎 Looking up domain...")
    data = await get_domain_info(domain_name)

    if not data or not getattr(data, "domain_name", None):
        return await status.edit("⚠️ Failed to retrieve WHOIS data.")

    response = await format_info(data, domain_name)
    await status.edit(response)
