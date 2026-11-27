# Authored By Certified Coders © 2025
import asyncio
from datetime import datetime
from pyrogram import filters
from AnnieXMedia import app, userbot
from config import BOT_USERNAME, OWNER_ID

_botschk_lock = asyncio.Lock()


@app.on_message(filters.command("botschk") & filters.group)
async def check_bots_command(client, message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply_text("🚫 You are not authorized to use this command.")

    client_ub = getattr(userbot, "one", None)
    if not client_ub or not getattr(client_ub, "is_connected", False):
        return await message.reply_text("❌ Userbot assistant 1 is not connected.")

    try:
        processing_msg = await message.reply_photo(
            photo="https://graph.org/file/e6b215db83839e8edf831.jpg",
            caption="**ᴄʜᴇᴄᴋɪɴɢ ʙᴏᴛs sᴛᴀᴛs ᴀʟɪᴠᴇ ᴏʀ ᴅᴇᴀᴅ...**"
        )
    except Exception:
        processing_msg = await message.reply_text("**ᴄʜᴇᴄᴋɪɴɢ ʙᴏᴛs sᴛᴀᴛs ᴀʟɪᴠᴇ ᴏʀ ᴅᴇᴀᴅ...**")

    start_time = datetime.now()

    bot_targets = [app.username or BOT_USERNAME]
    if len(message.command) > 1:
        bot_targets = [u.lstrip("@") for u in message.command[1:11]]

    response = "**ʙᴏᴛs sᴛᴀᴛᴜs ᴅᴇᴀᴅ ᴏʀ ᴀʟɪᴠᴇ ᴄʜᴇᴄᴋᴇʀ**\n\n"

    async with _botschk_lock:
        for bot_username in bot_targets:
            safe_u = bot_username.replace("[", "").replace("]", "").replace("`", "'")
            try:
                bot = await client_ub.get_users(bot_username)
                await asyncio.sleep(0.5)
                await client_ub.send_message(bot.id, "/start")
                await asyncio.sleep(3)

                async for bot_message in client_ub.get_chat_history(bot.id, limit=1):
                    status = "ᴏɴʟɪɴᴇ ✨" if bot_message.from_user and bot_message.from_user.id == bot.id else "ᴏғғʟɪɴᴇ ❄"
                    response += f"╭⎋ {bot.mention}\n╰⊚ **sᴛᴀᴛᴜs: {status}**\n\n"
            except Exception:
                response += f"╭⎋ @{safe_u}\n╰⊚ **sᴛᴀᴛᴜs: ᴇʀʀᴏʀ ❌**\n\n"

    last_checked_time = start_time.strftime("%Y-%m-%d")
    full_text = f"{response}⏲️ ʟᴀsᴛ ᴄʜᴇᴄᴋ: {last_checked_time}"
    is_media = bool(getattr(processing_msg, "photo", None) or getattr(processing_msg, "video", None))
    try:
        if is_media:
            await processing_msg.edit_caption(full_text[:1024])
        else:
            await processing_msg.edit_text(full_text[:4096])
    except Exception:
        await message.reply_text(full_text[:4096])
