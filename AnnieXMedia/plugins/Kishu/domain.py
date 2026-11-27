# Authored By Certified Coders © 2025
import asyncio
import socket
from datetime import datetime, timezone
import httpx
import whois
from pyrogram import filters

from AnnieXMedia import app


async def get_domain_info(domain_name):
    try:
        return await asyncio.to_thread(whois.whois, domain_name)
    except Exception as e:
        print(f"[WHOIS Error] {e}")
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


async def get_ip_location(ip):
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}")
            if resp.status_code == 200:
                data = resp.json()
                return data if data.get("status") == "success" else None
    except Exception as e:
        print(f"[IP Geo Error] {e}")
    return None


async def format_info(info):
    def clean(item):
        if isinstance(item, list):
            return item[0] if item else None
        return item

    domain = clean(info.domain_name)
    registrar = clean(info.registrar)
    creation = clean(info.creation_date)
    expiry = clean(info.expiration_date)
    nameservers = ', '.join(info.name_servers) if info.name_servers else "N/A"
    age = get_domain_age(creation)

    try:
        ip = await asyncio.to_thread(socket.gethostbyname, domain)
    except Exception:
        ip = "Unavailable"

    location_data = await get_ip_location(ip) if ip != "Unavailable" else None
    location = f"{location_data['country']}, {location_data['city']}" if location_data else "Unavailable"

    return (
        f"**ᴅᴏᴍᴀɪɴ ɴᴀᴍᴇ**: {domain}\n"
        f"**ʀᴇɢɪsᴛʀᴀʀ**: {registrar}\n"
        f"**ᴄʀᴇᴀᴛɪᴏɴ ᴅᴀᴛᴇ**: {creation.strftime('%Y-%m-%d') if hasattr(creation, 'strftime') else (creation or 'N/A')}\n"
        f"**ᴇxᴘɪʀᴀᴛɪᴏɴ ᴅᴀᴛᴇ**: {expiry.strftime('%Y-%m-%d') if hasattr(expiry, 'strftime') else (expiry or 'N/A')}\n"
        f"**ᴅᴏᴍᴀɪɴ ᴀɢᴇ**: {age if age is not None else 'N/A'} years\n"
        f"**ɪᴘ ᴀᴅᴅʀᴇss**: `{ip}`\n"
        f"**ʟᴏᴄᴀᴛɪᴏɴ**: {location}\n"
        f"**ɴᴀᴍᴇsᴇʀᴠᴇʀs**: {nameservers}\n"
    )


@app.on_message(filters.command("domain"))
async def domain_lookup(_, message):
    if len(message.command) < 2:
        return await message.reply("Please provide a domain name. Example: `/domain heroku.com`")

    domain_name = message.text.split(maxsplit=1)[1].strip()
    status = await message.reply("🔎 Looking up domain...")
    data = await get_domain_info(domain_name)

    if not data:
        return await status.edit("⚠️ Failed to retrieve WHOIS data.")

    response = await format_info(data)
    await status.edit(response)
