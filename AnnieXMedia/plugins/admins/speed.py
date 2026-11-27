# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS, adminlist
from AnnieXMedia import app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.misc import SUDOERS, db
from AnnieXMedia.utils import AdminRightsCheck
from AnnieXMedia.utils.database import get_cmode, is_active_chat, is_nonadmin_chat
from AnnieXMedia.utils.decorators.language import languageCB
from AnnieXMedia.utils.inline import close_markup, speed_markup

checker = []


@app.on_message(
    filters.command(["cspeed", "speed", "cslow", "slow", "playback", "cplayback"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def playback(cli, message: Message, _, chat_id):
    playing = db.get(chat_id)
    if not playing:
        return await message.reply_text(_["queue_2"])
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await message.reply_text(_["admin_27"])
    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        return await message.reply_text(_["admin_27"])
    upl = speed_markup(_, chat_id)
    return await message.reply_text(
        text=_["admin_28"].format(app.mention),
        reply_markup=upl,
    )


@app.on_callback_query(filters.regex("SpeedUP") & ~BANNED_USERS)
@languageCB
async def manage_callback(client, CallbackQuery, _):
    if not CallbackQuery.from_user or not CallbackQuery.message:
        return await CallbackQuery.answer("Action not allowed.", show_alert=True)
    parts = CallbackQuery.data.strip().split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return
    chat, speed = parts[1].split("|", 1)
    try:
        chat_id = int(chat)
    except ValueError:
        return
    allowed = {CallbackQuery.message.chat.id}
    cmode_id = await get_cmode(CallbackQuery.message.chat.id)
    if cmode_id:
        allowed.add(cmode_id)
    if chat_id not in allowed:
        return await CallbackQuery.answer("Unauthorized chat control.", show_alert=True)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
    if not is_non_admin:
        if CallbackQuery.from_user.id not in SUDOERS:
            admins = adminlist.get(CallbackQuery.message.chat.id)
            if not admins:
                return await CallbackQuery.answer(_["admin_13"], show_alert=True)
            else:
                if CallbackQuery.from_user.id not in admins:
                    return await CallbackQuery.answer(_["admin_14"], show_alert=True)
    playing = db.get(chat_id)
    if not playing:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return await CallbackQuery.answer(_["admin_27"], show_alert=True)
    file_path = playing[0]["file"]
    if "downloads" not in file_path:
        return await CallbackQuery.answer(_["admin_27"], show_alert=True)
    checkspeed = (playing[0]).get("speed")
    if checkspeed:
        if str(checkspeed) == str(speed):
            if str(speed) == str("1.0"):
                return await CallbackQuery.answer(
                    _["admin_29"],
                    show_alert=True,
                )
    else:
        if str(speed) == str("1.0"):
            return await CallbackQuery.answer(
                _["admin_29"],
                show_alert=True,
            )
    if chat_id in checker:
        return await CallbackQuery.answer(
            _["admin_30"],
            show_alert=True,
        )
    checker.append(chat_id)
    try:
        try:
            await CallbackQuery.answer(_["admin_31"])
        except Exception:
            pass
        user_mention = CallbackQuery.from_user.mention if CallbackQuery.from_user else "Admin"
        mystic = await CallbackQuery.edit_message_text(
            text=_["admin_32"].format(user_mention),
        )
        try:
            await StreamController.speedup_stream(
                chat_id,
                file_path,
                speed,
                playing,
            )
        except Exception:
            return await mystic.edit_text(_["admin_33"], reply_markup=close_markup(_))
        await mystic.edit_text(
            text=_["admin_34"].format(speed, user_mention),
            reply_markup=close_markup(_),
        )
    finally:
        if chat_id in checker:
            checker.remove(chat_id)
