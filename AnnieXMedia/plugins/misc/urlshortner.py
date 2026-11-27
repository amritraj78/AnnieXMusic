# Authored By Certified Coders © 2025
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton as ikb, InlineKeyboardMarkup as ikm, Message
from pyrogram.enums import ChatAction, ParseMode
from AnnieXMedia import app
import asyncio
import socket
import ipaddress
from urllib.parse import urljoin, urlparse
import pyshorteners
import httpx


shortener = pyshorteners.Shortener()


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


def _shorten_sync(link: str) -> list[tuple[str, str]]:
    providers = (
        ("TinyURL", "tinyurl"),
        ("Clck.ru", "clckru"),
        ("Dagd", "dagd"),
    )
    results: list[tuple[str, str]] = []
    for label, attr in providers:
        try:
            short_url = str(getattr(shortener, attr).short(link) or "").strip()
            if short_url.startswith(("http://", "https://")):
                results.append((label, short_url))
        except Exception:
            continue
    return results


@app.on_message(filters.command("short"))
async def short_urls(bot: Client, message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide a link to shorten.\n\n**Example:** `/short https://example.com`",
            parse_mode=ParseMode.MARKDOWN
        )

    link = message.command[1]
    if not await is_safe_url(link):
        return await message.reply_text("❌ Invalid or restricted URL.", parse_mode=ParseMode.MARKDOWN)

    try:
        shortened = await asyncio.to_thread(_shorten_sync, link)
        if not shortened:
            return await message.reply_text("❌ All URL shortener providers failed. Please try again later.")

        buttons = [ikb(f"🔗 {label}", url=short_url) for label, short_url in shortened]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        markup = ikm(rows)

        await message.reply_text("🔍 Here are your shortened URLs:", reply_markup=markup)

    except Exception as e:
        print(f"Shortener error: {e}")
        await message.reply_text("❌ Failed to shorten the link. It might already be shortened or invalid.")


@app.on_message(filters.command("unshort"))
async def unshort_url(bot: Client, message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide a shortened link.\n\n**Example:** `/unshort https://bit.ly/example`",
            parse_mode=ParseMode.MARKDOWN
        )

    current_url = message.command[1]

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            for _ in range(5):
                if not await is_safe_url(current_url):
                    return await message.reply_text("❌ Invalid or restricted URL.", parse_mode=ParseMode.MARKDOWN)
                response = await client.get(current_url)
                if response.is_redirect and "location" in response.headers:
                    current_url = urljoin(current_url, response.headers["location"])
                    continue
                break
        if not await is_safe_url(current_url):
            return await message.reply_text("❌ Final redirect points to a restricted address.", parse_mode=ParseMode.MARKDOWN)
        final_url = current_url

        markup = ikm([[ikb("🔗 View Final URL", url=final_url)]])
        await message.reply_text(f"✅ **Unshortened URL:**\n`{final_url}`", reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print(f"Unshortener error: {e}")
        await message.reply_text("❌ Failed to unshorten the link. It may be broken or invalid.")
