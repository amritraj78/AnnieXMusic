# Authored By Certified Coders © 2025
import random
import httpx
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from AnnieXMedia import app
from config import SUPPORT_CHAT

SUPPORT_BTN = InlineKeyboardMarkup(
    [[InlineKeyboardButton("ꜱᴜᴘᴘᴏʀᴛ", url=SUPPORT_CHAT)]]
)

CUTE_VIDEO = "https://telegra.ph/file/528d0563175669e123a75.mp4"


@app.on_message(filters.command("wish"))
async def wish(_, m):
    if len(m.command) < 2:
        return await m.reply_text("❌ ᴀᴅᴅ ʏᴏᴜʀ ᴡɪꜱʜ ʙᴀʙʏ 🥀!")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://nekos.best/api/v2/happy")
            if resp.status_code != 200:
                raise Exception("API status error")
            api = resp.json()
            results = api.get("results", [])
            if not results:
                raise Exception("Empty results")
            url = results[0]["url"]
    except Exception:
        return await m.reply_text("⚠️ Couldn't fetch animation, try again later.")

    text = m.text.split(None, 1)[1]
    wish_count = random.randint(1, 100)
    name = (m.from_user.first_name if m.from_user else "User") or "User"

    caption = (
        f"✨ ʜᴇʏ {name}!\n"
        f"🪄 ʏᴏᴜʀ ᴡɪꜱʜ: {text}\n"
        f"📊 ᴘᴏꜱꜱɪʙɪʟɪᴛʏ: {wish_count}%"
    )

    try:
        await app.send_animation(
            chat_id=m.chat.id,
            animation=url,
            caption=caption,
            reply_markup=SUPPORT_BTN,
        )
    except Exception:
        await m.reply_text(caption, reply_markup=SUPPORT_BTN)


@app.on_message(filters.command("cute"))
async def cute(_, message):
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.from_user:
        target = message.from_user

    if target:
        mention = f"[{target.first_name}](tg://user?id={target.id})"
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
