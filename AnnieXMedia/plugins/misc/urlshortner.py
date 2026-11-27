# Authored By Certified Coders © 2025
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton as ikb, InlineKeyboardMarkup as ikm, Message
from pyrogram.enums import ChatAction, ParseMode
from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.security import fetch_url_limited, is_safe_http_url
import asyncio
import pyshorteners


shortener = pyshorteners.Shortener()


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

    link = message.command[1].strip()
    if not await is_safe_http_url(link):
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
        LOGGER(__name__).warning(f"Shortener error: {e}")
        await message.reply_text("❌ Failed to shorten the link. It might already be shortened or invalid.")


@app.on_message(filters.command("unshort"))
async def unshort_url(bot: Client, message: Message):
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide a shortened link.\n\n**Example:** `/unshort https://bit.ly/example`",
            parse_mode=ParseMode.MARKDOWN
        )

    raw_url = message.command[1].strip()

    try:
        ok, status, final_or_err, _ = await fetch_url_limited(
            raw_url,
            max_bytes=4096,
            max_redirects=5,
            timeout=10.0,
            head_only_redirects=True,
        )
        if ok and status == 405:
            ok, status, final_or_err, _ = await fetch_url_limited(
                raw_url,
                max_bytes=65536,
                max_redirects=5,
                timeout=10.0,
                head_only_redirects=False,
            )
        if not ok or not final_or_err.startswith(("http://", "https://")):
            safe_err = final_or_err.replace("`", "'")
            return await message.reply_text(
                f"❌ {safe_err}",
                parse_mode=ParseMode.MARKDOWN,
            )

        final_url = final_or_err
        safe_final = final_url.replace("`", "'")
        markup = ikm([[ikb("🔗 View Final URL", url=final_url)]])
        await message.reply_text(
            f"✅ **Unshortened URL:**\n`{safe_final}`",
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        LOGGER(__name__).warning(f"Unshortener error: {e}")
        await message.reply_text("❌ Failed to unshorten the link. It may be broken or invalid.")
