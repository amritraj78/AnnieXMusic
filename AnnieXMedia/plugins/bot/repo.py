# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from AnnieXMedia import app
from config import BOT_USERNAME, OWNER_USERNAME, SUPPORT_CHANNEL, SUPPORT_CHAT, UPSTREAM_REPO

repo_caption = """**
🚀 ᴀᴍʀɪᴛ ᴍᴜsɪᴄ – ʀᴇᴘᴏsɪᴛᴏʀʏ 🚀

➤ ᴅᴇᴘʟᴏʏ ᴇᴀsɪʟʏ ᴏɴ ᴋᴏʏᴇʙ ғʀᴇᴇ / ᴠᴘs / ᴅᴏᴄᴋᴇʀ
➤ ʟᴀɢ ꜰʀᴇᴇ ᴍᴜsɪᴄ + ᴠɪᴅᴇᴏ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ sᴛʀᴇᴀᴍɪɴɢ
➤ ʜɪɢʜ sᴇᴄᴜʀɪᴛʏ & 24/7 sᴛᴀʙʟᴇ

ɪꜰ ʏᴏᴜ ꜰᴀᴄᴇ ᴀɴʏ ᴘʀᴏʙʟᴇᴍ, ᴊᴏɪɴ ᴏᴜʀ ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ
**"""

@app.on_message(filters.command("repo"))
async def show_repo(_, msg):
    buttons = [
        [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ ✨", url=f"https://t.me/{app.username or BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("👑 ᴏᴡɴᴇʀ", url=f"https://t.me/{OWNER_USERNAME}"),
            InlineKeyboardButton("📢 ᴄʜᴀɴɴᴇʟ", url=SUPPORT_CHANNEL)
        ],
        [
            InlineKeyboardButton("🛠️ ꜱᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url=SUPPORT_CHAT),
            InlineKeyboardButton("🎵 ɢɪᴛʜᴜʙ", url=UPSTREAM_REPO)
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    try:  
        await msg.reply_photo(
            photo="https://telegra.ph/file/58afe55fee5ae99d6901b.jpg",
            caption=repo_caption,
            reply_markup=reply_markup
        )
    except Exception:
        try:
            await msg.reply_text(
                text=repo_caption,
                reply_markup=reply_markup
            )
        except Exception:
            pass
