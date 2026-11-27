# Authored By Certified Coders © 2025
import asyncio
import random
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, LinkPreviewOptions
from config import (
    BANNED_USERS,
    lyrical,
    SOUNCLOUD_IMG_URL,
    STREAM_IMG_URL,
    SUPPORT_CHAT,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
)
from strings import get_string
from AnnieXMedia import YouTube, app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_assistant,
    get_cmode,
    get_lang,
    is_active_chat,
    is_music_playing,
    music_off,
    music_on,
    set_loop,
)
from AnnieXMedia.utils.decorators import ActualAdminCB, languageCB
from AnnieXMedia.utils.formatters import seconds_to_min
from AnnieXMedia.utils.inline import close_markup, stream_markup, stream_markup_timer
from AnnieXMedia.utils.stream.autoclear import auto_clean
from AnnieXMedia.utils.thumbnails import get_thumb


checker = {}


def parse_chat_info(chat_info: str):
    if "_" in chat_info:
        parts = chat_info.split("_")
        return int(parts[0]), parts[1]
    return int(chat_info), None


@app.on_callback_query(filters.regex("unban_assistant") & ~BANNED_USERS)
@ActualAdminCB
async def unban_assistant(_, callback: CallbackQuery, _lang):
    if not callback.message or not callback.message.chat:
        return
    chat_id = callback.message.chat.id
    userbot = await get_assistant(chat_id)
    if not userbot or not getattr(userbot, "id", None):
        return await callback.answer("Assistant unavailable.", show_alert=True)
    try:
        await app.unban_chat_member(chat_id, userbot.id)
        await callback.answer(
            "ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ ᴜɴʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ🥰🥳\n\n➻ ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ sᴏɴɢs🫠🔉\n\nTʜᴀɴᴋ ʏᴏᴜ💗",
            show_alert=True,
        )
    except Exception:
        await callback.answer(
            "Fᴀɪʟᴇᴅ ᴛᴏ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ʙᴀɴ ᴘᴏᴡᴇʀ\n\n➻ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ʙᴀɴ ᴘᴏᴡᴇʀ sᴏ ᴛʜᴀᴛ ɪ ᴄᴀɴ ᴜɴʙᴀɴ ᴍʏ ᴀssɪsᴛᴀɴᴛ ɪᴅ",
            show_alert=True,
        )


@app.on_callback_query(filters.regex("stream_admin") & ~BANNED_USERS)
@ActualAdminCB
async def manage_callback(client, callback: CallbackQuery, _):
    parts = (callback.data or "").strip().split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return
    command, chat_info = parts[1].split("|", 1)
    try:
        chat_id, counter = parse_chat_info(chat_info)
    except ValueError:
        return
    msg_chat_id = callback.message.chat.id if callback.message and callback.message.chat else 0
    allowed_chats = {msg_chat_id}
    cmode_chat = await get_cmode(msg_chat_id)
    if cmode_chat:
        allowed_chats.add(cmode_chat)
    if chat_id not in allowed_chats:
        return await callback.answer("Unauthorized chat control.", show_alert=True)
    if not await is_active_chat(chat_id):
        return await callback.answer(_["general_5"], show_alert=True)
    user_mention = callback.from_user.mention if callback.from_user else "Admin"
    
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await callback.answer(_["admin_1"], show_alert=True)
        await callback.answer()
        await music_off(chat_id)
        await StreamController.pause_stream(chat_id)
        await callback.message.reply_text(_["admin_2"].format(user_mention), reply_markup=close_markup(_))

    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await callback.answer(_["admin_3"], show_alert=True)
        await callback.answer()
        await music_on(chat_id)
        await StreamController.resume_stream(chat_id)
        await callback.message.reply_text(_["admin_4"].format(user_mention), reply_markup=close_markup(_))

    elif command in ["Stop", "End"]:
        await callback.answer()
        await StreamController.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await callback.message.reply_text(_["admin_5"].format(user_mention), reply_markup=close_markup(_))
        await callback.message.delete()

    elif command == "Loop":
        await callback.answer()
        await set_loop(chat_id, 3)
        await callback.message.reply_text(_["admin_41"].format(user_mention, 3))

    elif command == "Shuffle":
        playlist = db.get(chat_id)
        if not playlist:
            return await callback.answer(_["admin_42"], show_alert=True)
        try:
            popped = playlist.pop(0)
        except Exception:
            return await callback.answer(_["admin_43"], show_alert=True)
        if not playlist:
            playlist.insert(0, popped)
            return await callback.answer(_["admin_43"], show_alert=True)
        await callback.answer()
        random.shuffle(playlist)
        playlist.insert(0, popped)
        await callback.message.reply_text(_["admin_44"].format(user_mention))

    elif command in ["Skip", "Replay"]:
        await handle_skip_replay(callback, _, chat_id, command, user_mention)

    else:
        await handle_seek(callback, _, chat_id, command, user_mention)


async def _update_stream_card(callback: CallbackQuery, text_msg: str, reply_markup=None):
    try:
        if callback.message and (callback.message.photo or callback.message.video):
            await callback.edit_message_caption(caption=text_msg, reply_markup=reply_markup)
        else:
            await callback.edit_message_text(text_msg, reply_markup=reply_markup)
    except Exception:
        try:
            await callback.message.reply_text(text_msg, reply_markup=reply_markup)
        except Exception:
            pass


async def handle_skip_replay(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    playlist = db.get(chat_id)

    if not playlist or len(playlist) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)

    if command == "Skip":
        text_msg = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {user_mention} 🥀"
        try:
            popped = playlist.pop(0)
            if popped:
                await auto_clean(popped)
            if not playlist:
                await callback.answer()
                await _update_stream_card(callback, text_msg)
                try:
                    await callback.message.reply_text(
                        _["admin_6"].format(user_mention, callback.message.chat.title or "Chat"),
                        reply_markup=close_markup(_),
                    )
                except Exception:
                    pass
                return await StreamController.stop_stream(chat_id)
        except Exception:
            await _update_stream_card(callback, text_msg)
            return await StreamController.stop_stream(chat_id)
    else:
        text_msg = f"➻ sᴛʀᴇᴀᴍ ʀᴇᴩʟᴀʏᴇᴅ 🔁\n│ \n└ʙʏ : {user_mention} 🥀"

    if len(playlist) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)

    await callback.answer()

    current_track = playlist[0]
    queued = current_track["file"]
    title = current_track["title"].title()
    user = current_track["by"]
    duration = current_track["dur"]
    streamtype = current_track["streamtype"]
    videoid = current_track["vidid"]
    status = True if str(streamtype) == "video" else None

    db[chat_id][0]["played"] = 0
    if current_track.get("old_dur"):
        db[chat_id][0]["dur"] = current_track["old_dur"]
        db[chat_id][0]["seconds"] = current_track["old_second"]
        db[chat_id][0]["speed_path"] = None
        db[chat_id][0]["speed"] = 1.0

    if "live_" in queued:
        n, new_link = await YouTube.video(videoid, True)
        if n == 0:
            return await callback.message.reply_text(
                _["admin_7"].format(title),
                reply_markup=close_markup(_)
            )
        try:
            image = await YouTube.thumbnail(videoid, True)
        except Exception:
            image = None
        try:
            await StreamController.skip_stream(chat_id, new_link, video=status, image=image)
        except Exception:
            return await callback.message.reply_text(_["call_6"])
        buttons = stream_markup(_, chat_id)
        img = await get_thumb(videoid)
        run = await callback.message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration, user),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
        await _update_stream_card(callback, text_msg, close_markup(_))

    elif "vid_" in queued:
        mystic = await callback.message.reply_text(_["call_7"], link_preview_options=LinkPreviewOptions(is_disabled=True))
        try:
            file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=status, title=title)
        except Exception:
            return await mystic.edit_text(_["call_6"])
        try:
            image = await YouTube.thumbnail(videoid, True)
        except Exception:
            image = None
        try:
            await StreamController.skip_stream(chat_id, file_path, video=status, image=image)
        except Exception:
            return await mystic.edit_text(_["call_6"])
        buttons = stream_markup(_, chat_id)
        img = await get_thumb(videoid)
        run = await callback.message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration, user),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        await _update_stream_card(callback, text_msg, close_markup(_))
        await mystic.delete()

    elif "index_" in queued:
        try:
            await StreamController.skip_stream(chat_id, videoid, video=status)
        except Exception:
            return await callback.message.reply_text(_["call_6"])
        buttons = stream_markup(_, chat_id)
        run = await callback.message.reply_photo(
            photo=STREAM_IMG_URL,
            caption=_["stream_2"].format(user),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
        await _update_stream_card(callback, text_msg, close_markup(_))

    else:
        if videoid in ["telegram", "soundcloud"]:
            image = None
        else:
            try:
                image = await YouTube.thumbnail(videoid, True)
            except Exception:
                image = None
        try:
            await StreamController.skip_stream(chat_id, queued, video=status, image=image)
        except Exception:
            return await callback.message.reply_text(_["call_6"])
        if videoid == "telegram":
            buttons = stream_markup(_, chat_id)
            run = await callback.message.reply_photo(
                photo=(TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else TELEGRAM_VIDEO_URL),
                caption=_["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif videoid == "soundcloud":
            buttons = stream_markup(_, chat_id)
            run = await callback.message.reply_photo(
                photo=(SOUNCLOUD_IMG_URL if str(streamtype) == "audio" else TELEGRAM_VIDEO_URL),
                caption=_["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        else:
            buttons = stream_markup(_, chat_id)
            img = await get_thumb(videoid)
            run = await callback.message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration, user),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
        await _update_stream_card(callback, text_msg, close_markup(_))


async def handle_seek(callback: CallbackQuery, _, chat_id: int, command: str, user_mention: str):
    if command not in ("1", "2", "3", "4"):
        return await callback.answer("Invalid seek command.", show_alert=True)
    playing = db.get(chat_id)
    if not playing or len(playing) == 0:
        return await callback.answer(_["queue_2"], show_alert=True)
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await callback.answer(_["admin_22"], show_alert=True)
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return await callback.answer(_["admin_22"], show_alert=True)
    duration_played = int(playing[0]["played"])
    duration_to_skip = 10 if int(command) in [1, 2] else 30
    duration = playing[0]["dur"]
    if int(command) in [1, 3]:
        if (duration_played - duration_to_skip) <= 10:
            bet = seconds_to_min(duration_played)
            return await callback.answer(
                f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                show_alert=True
            )
        to_seek = duration_played - duration_to_skip + 1
    else:
        if (duration_seconds - (duration_played + duration_to_skip)) <= 10:
            bet = seconds_to_min(duration_played)
            return await callback.answer(
                f"» ʙᴏᴛ ɪs ᴜɴᴀʙʟᴇ ᴛᴏ sᴇᴇᴋ ʙᴇᴄᴀᴜsᴇ ᴛʜᴇ ᴅᴜʀᴀᴛɪᴏɴ ᴇxᴄᴇᴇᴅs.\n\n"
                f"ᴄᴜʀʀᴇɴᴛʟʏ ᴩʟᴀʏᴇᴅ :** {bet}** ᴍɪɴᴜᴛᴇs ᴏᴜᴛ ᴏғ **{duration}** ᴍɪɴᴜᴛᴇs.",
                show_alert=True
            )
        to_seek = duration_played + duration_to_skip + 1
    await callback.answer()
    mystic = await callback.message.reply_text(_["admin_24"])
    if "vid_" in file_path:
        n, file_path = await YouTube.video(playing[0]["vidid"], True)
        if n == 0:
            return await mystic.edit_text(_["admin_22"])
    try:
        await StreamController.seek_stream(
            chat_id,
            file_path,
            seconds_to_min(to_seek),
            duration,
            playing[0]["streamtype"],
        )
    except Exception:
        return await mystic.edit_text(_["admin_26"])
    if int(command) in [1, 3]:
        db[chat_id][0]["played"] -= duration_to_skip
    else:
        db[chat_id][0]["played"] += duration_to_skip
    seek_message = _["admin_25"].format(seconds_to_min(to_seek))
    await mystic.edit_text(f"{seek_message}\n\nᴄʜᴀɴɢᴇs ᴅᴏɴᴇ ʙʏ : {user_mention} !")


async def markup_timer():
    while True:
        await asyncio.sleep(6)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                mystic = playing[0].get("mystic")
                if not mystic:
                    continue
                if chat_id in checker and mystic.id in checker[chat_id]:
                    if checker[chat_id][mystic.id] is False:
                        continue
                try:
                    language = await get_lang(chat_id)
                    _lang = get_string(language)
                except Exception:
                    _lang = get_string("en")
                try:
                    buttons = stream_markup_timer(
                        _lang,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                    )
                    if buttons:
                        await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
                except Exception:
                    continue
            except Exception:
                continue


try:
    asyncio.get_running_loop().create_task(markup_timer())
except RuntimeError:
    pass


@app.on_callback_query(filters.regex(r"^(?:close|close_data)$") & ~BANNED_USERS)
async def close_menu(_, query: CallbackQuery):
    try:
        await query.answer()
        if not query.message:
            return
        chat = query.message.chat
        await query.message.delete()
        user_mention = query.from_user.mention if query.from_user else "Admin"
        msg = await app.send_message(chat.id, f"✅ ᴄʟᴏꜱᴇᴅ ʙʏ : {user_mention}")
        await asyncio.sleep(2)
        await msg.delete()
    except Exception:
        pass


@app.on_callback_query(filters.regex("stop_downloading") & ~BANNED_USERS)
@ActualAdminCB
async def stop_download(_, query: CallbackQuery, _lang):
    task = lyrical.get(query.message.id)
    if not task:
        return await query.answer(_lang["tg_4"], show_alert=True)
    if task.done() or task.cancelled():
        return await query.answer(_lang["tg_5"], show_alert=True)
    try:
        task.cancel()
        lyrical.pop(query.message.id, None)
        await query.answer(_lang["tg_6"], show_alert=True)
        user_mention = query.from_user.mention if query.from_user else "Admin"
        return await query.edit_message_text(_lang["tg_7"].format(user_mention))
    except Exception:
        return await query.answer(_lang["tg_8"], show_alert=True)
