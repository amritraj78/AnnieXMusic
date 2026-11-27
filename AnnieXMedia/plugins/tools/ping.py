# Authored By Certified Coders © 2025
from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.utils import bot_sys_stats
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.inline import supp_markup
from config import BANNED_USERS, PING_VID_URL


@app.on_message(filters.command("ping", prefixes=["/", "."]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()
    is_media = True
    try:
        response = await message.reply_video(
            video=PING_VID_URL,
            caption=_["ping_1"].format(app.mention),
        )
    except Exception:
        is_media = False
        response = await message.reply_text(_["ping_1"].format(app.mention))

    pytgping = await StreamController.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = round((datetime.now() - start).total_seconds() * 1000, 2)
    text = _["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping)
    markup = supp_markup(_)

    try:
        if is_media:
            await response.edit_caption(text, reply_markup=markup)
        else:
            await response.edit_text(text, reply_markup=markup)
    except Exception:
        try:
            await response.edit_text(text, reply_markup=markup)
        except Exception:
            pass
