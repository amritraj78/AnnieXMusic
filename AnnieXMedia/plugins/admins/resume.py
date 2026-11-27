# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.utils.database import is_music_playing, music_on
from AnnieXMedia.utils.decorators import AdminRightsCheck
from AnnieXMedia.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(filters.command(["resume", "cresume"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def resume_com(cli, message: Message, _, chat_id):
    if await is_music_playing(chat_id):
        return await message.reply_text(_["admin_3"])
    await music_on(chat_id)
    await StreamController.resume_stream(chat_id)
    user_mention = message.from_user.mention if message.from_user else "Admin"
    await message.reply_text(
        _["admin_4"].format(user_mention), reply_markup=close_markup(_)
    )
