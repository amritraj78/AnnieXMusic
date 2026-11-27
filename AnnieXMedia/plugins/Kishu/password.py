# Authored By Certified Coders © 2025
import html
import secrets
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from AnnieXMedia import app
from config import BOT_USERNAME


@app.on_message(filters.command(["genpassword", "genpw"]))
async def password(bot, message):
    processing = await message.reply_text("Pʀᴏᴄᴇꜱꜱɪɴɢ...")

    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*()_+"
    
    if len(message.command) > 1:
        parts = (message.text or message.caption or "").split(None, 1)
        input_length = parts[1] if len(parts) > 1 else ""
    else:
        input_length = secrets.choice(["5", "6", "7", "8", "9", "10", "12", "14"])

    try:
        length = int(input_length)
        if length < 1 or length > 128:
            return await processing.edit_text("Password length must be between 1 and 128.")
    except ValueError:
        return await processing.edit_text("Please enter a valid positive number for the password length (1-128).")

    generated_password = "".join(secrets.choice(characters) for _ in range(length))

    reply_text = (
        f"<b>Lɪᴍɪᴛ:</b> {length}\n"
        f"<b>Pᴀꜱꜱᴡᴏʀᴅ:</b> <code>{html.escape(generated_password)}</code>"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("𝗔𝗗𝗗 𝗠𝗘", url=f"https://t.me/{app.username or BOT_USERNAME}?startgroup=true")]
    ])

    await processing.edit_text(reply_text, reply_markup=buttons, parse_mode=enums.ParseMode.HTML)
