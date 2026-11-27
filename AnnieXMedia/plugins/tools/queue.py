# Authored By Certified Coders © 2025
import asyncio
import os

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InputMediaPhoto, Message

import config
from AnnieXMedia import app
from AnnieXMedia.misc import db
from AnnieXMedia.utils import ANNIEBIN, get_channeplayCB, seconds_to_min
from AnnieXMedia.utils.database import get_cmode, is_active_chat, is_music_playing
from AnnieXMedia.utils.decorators.language import language, languageCB
from AnnieXMedia.utils.inline import queue_back_markup, queue_markup
from config import BANNED_USERS

basic: dict[tuple[int, str], bool] = {}


def _set_basic(chat_id: int, videoid: str, val: bool) -> None:
    if len(basic) > 1000:
        basic.clear()
    basic[(chat_id, videoid)] = val


def get_image(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"
    else:
        return config.YOUTUBE_IMG_URL


def get_duration(playing):
    file_path = playing[0].get("file", "")
    if "index_" in file_path or "live_" in file_path:
        return "Unknown"
    try:
        duration_seconds = int(playing[0].get("seconds", 0))
    except (ValueError, TypeError):
        return "Unknown"
    if duration_seconds == 0:
        return "Unknown"
    else:
        return "Inline"


@app.on_message(
    filters.command(["queue", "cqueue", "player", "cplayer", "playing", "cplaying"])
    & filters.group
    & ~BANNED_USERS
)
@language
async def get_queue(client, message: Message, _):
    if message.command[0][0] == "c":
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(_["setting_7"])
        try:
            await app.get_chat(chat_id)
        except Exception:
            return await message.reply_text(_["cplay_4"])
        cplay = True
    else:
        chat_id = message.chat.id
        cplay = False
    if not await is_active_chat(chat_id):
        return await message.reply_text(_["general_5"])
    got = db.get(chat_id)
    if not got:
        return await message.reply_text(_["queue_2"])
    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    if "live_" in file:
        IMAGE = get_image(videoid)
    elif "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (
                config.TELEGRAM_AUDIO_URL
                if typo == "Audio"
                else config.TELEGRAM_VIDEO_URL
            )
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)
    upl = (
        queue_markup(_, DUR, "c" if cplay else "g", videoid)
        if DUR == "Unknown"
        else queue_markup(
            _,
            DUR,
            "c" if cplay else "g",
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )
    )
    _set_basic(chat_id, videoid, True)
    try:
        mystic = await message.reply_photo(IMAGE, caption=cap[:1024], reply_markup=upl)
    except Exception:
        mystic = await message.reply_text(cap[:4096], reply_markup=upl)
    if DUR != "Unknown":
        try:
            while db.get(chat_id) and db[chat_id][0].get("vidid") == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic.get((chat_id, videoid)) and db.get(chat_id):
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    "c" if cplay else "g",
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                            except Exception:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except Exception:
            return


@app.on_callback_query(filters.regex("GetTimer") & ~BANNED_USERS)
async def quite_timer(client, CallbackQuery: CallbackQuery):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass


@app.on_callback_query(filters.regex("GetQueued") & ~BANNED_USERS)
@languageCB
async def queued_tracks(client, CallbackQuery: CallbackQuery, _):
    if not CallbackQuery.message:
        return await CallbackQuery.answer()
    callback_data = CallbackQuery.data.strip()
    parts = callback_data.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return await CallbackQuery.answer()
    what, videoid = parts[1].split("|", 1)
    try:
        chat_id, channel = await get_channeplayCB(_, what, CallbackQuery)
    except Exception:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    if len(got) == 1:
        return await CallbackQuery.answer(_["queue_5"], show_alert=True)
    await CallbackQuery.answer()
    _set_basic(chat_id, videoid, False)
    buttons = queue_back_markup(_, what)
    queue_photo_url = "https://telegra.ph//file/6f7d35131f69951c74ee5.jpg"
    med = InputMediaPhoto(
        media=queue_photo_url,
        caption=_["queue_1"],
    )
    try:
        await CallbackQuery.edit_message_media(media=med)
    except Exception:
        pass
    msg = ""
    for j, x in enumerate(got, 1):
        if j == 1:
            msg += f'Streaming :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        elif j == 2:
            msg += f'Queued :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        else:
            msg += f'✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
    if "Queued" in msg and len(msg) >= 950:
        if "✨" in msg:
            msg = msg.replace("✨", "")
        link = await ANNIEBIN(msg)
        med = InputMediaPhoto(media=queue_photo_url, caption=_["queue_3"].format(link)[:1024])
        try:
            await CallbackQuery.edit_message_media(media=med, reply_markup=buttons)
        except Exception:
            await CallbackQuery.edit_message_caption(caption=_["queue_3"].format(link)[:1024], reply_markup=buttons)
    else:
        await asyncio.sleep(1)
        try:
            if CallbackQuery.message.photo or CallbackQuery.message.video:
                return await CallbackQuery.edit_message_caption(caption=msg[:1024], reply_markup=buttons)
            return await CallbackQuery.edit_message_text(msg[:4096], reply_markup=buttons)
        except Exception:
            return


@app.on_callback_query(filters.regex("queue_back_timer") & ~BANNED_USERS)
@languageCB
async def queue_back(client, CallbackQuery: CallbackQuery, _):
    if not CallbackQuery.message:
        return await CallbackQuery.answer()
    callback_data = CallbackQuery.data.strip()
    parts = callback_data.split(None, 1)
    if len(parts) < 2:
        return await CallbackQuery.answer()
    cplay = parts[1]
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except Exception:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer(_["set_cb_5"], show_alert=True)
    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    if "live_" in file:
        IMAGE = get_image(videoid)
    elif "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (
                config.TELEGRAM_AUDIO_URL
                if typo == "Audio"
                else config.TELEGRAM_VIDEO_URL
            )
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)
    upl = (
        queue_markup(_, DUR, cplay, videoid)
        if DUR == "Unknown"
        else queue_markup(
            _,
            DUR,
            cplay,
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )
    )
    _set_basic(chat_id, videoid, True)

    med = InputMediaPhoto(media=IMAGE, caption=cap[:1024])
    mystic = await CallbackQuery.edit_message_media(media=med, reply_markup=upl)
    if DUR != "Unknown":
        try:
            while db.get(chat_id) and db[chat_id][0].get("vidid") == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic.get((chat_id, videoid)) and db.get(chat_id):
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    cplay,
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                            except Exception:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except Exception:
            return
