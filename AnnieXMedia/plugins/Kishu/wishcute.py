# Authored By Certified Coders © 2025
import random
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from AnnieXMedia import app
from AnnieXMedia.core.http_pool import get_http_session
from config import SUPPORT_CHAT

SUPPORT_BTN = InlineKeyboardMarkup(
    [[InlineKeyboardButton("ꜱᴜᴘᴘᴏʀᴛ", url=SUPPORT_CHAT)]]
)

CUTE_VIDEO = "https://telegra.ph/file/528d0563175669e123a75.mp4"


def _clean_md(text: str) -> str:
    return (text or "").replace("[", "(").replace("]", ")").replace("`", "'")


@app.on_message(filters.command("wish"))
async def wish(_, m):
    if len(m.command) < 2:
        return await m.reply_text("❌ ᴀᴅᴅ ʏᴏᴜʀ ᴡɪꜱʜ ʙᴀʙʏ 🥀!")

    try:
        client = await get_http_session()
        async with client.get("https://nekos.best/api/v2/happy", timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                raise Exception("API status error")
            api = await resp.json(content_type=None)
            results = api.get("results", [])
            if not results:
                raise Exception("Empty results")
            url = results[0]["url"]
    except Exception:
        return await m.reply_text("⚠️ Couldn't fetch animation, try again later.")

    raw_parts = (m.text or m.caption or "").split(None, 1)
    text = _clean_md((raw_parts[1] if len(raw_parts) > 1 else "")[:500])
    wish_count = random.randint(1, 100)
    name = _clean_md((m.from_user.first_name if m.from_user else "User") or "User")

    caption = (
        f"✨ ʜᴇʏ {name}!\n"
        f"🪄 ʏᴏᴜʀ ᴡɪꜱʜ: {text}\n"
        f"📊 ᴘᴏꜱꜱɪʙɪʟɪᴛʏ: {wish_count}%"
    )

    try:
        await app.send_animation(
            chat_id=m.chat.id,
            animation=url,
            caption=caption[:1024],
            reply_markup=SUPPORT_BTN,
        )
    except Exception:
        await m.reply_text(caption[:4096], reply_markup=SUPPORT_BTN)


@app.on_message(filters.command("cute"))
async def cute(_, message):
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.from_user:
        target = message.from_user

    if target:
        safe_name = _clean_md(target.first_name or "User")
        mention = f"[{safe_name}](tg://user?id={target.id})"
    else:
        mention = "User"

    percent = random.randint(1, 100)
    caption = f"🍑 {mention} ɪꜱ {percent}% ᴄᴜᴛᴇ ʙᴀʙʏ 🥀"

    reply_to_id = message.reply_to_message.id if message.reply_to_message else None

    try:
        await app.send_document(
            chat_id=message.chat.id,
            document=CUTE_VIDEO,
            caption=caption,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=SUPPORT_BTN,
            reply_to_message_id=reply_to_id,
        )
    except Exception:
        await message.reply_text(
            caption,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=SUPPORT_BTN,
        )
