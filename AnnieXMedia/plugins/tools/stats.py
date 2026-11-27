# Authored By Certified Coders © 2025
import asyncio
import platform
from sys import version as pyver

import psutil
from pyrogram import __version__ as pyrover
from pyrogram import filters
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaVideo, Message
from pytgcalls.__version__ import __version__ as pytgver

import config
from AnnieXMedia import app
from AnnieXMedia.core.userbot import assistants
from AnnieXMedia.misc import SUDOERS, mongodb
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import (
    get_served_chats_count,
    get_served_users_count,
    get_sudoers,
)
from AnnieXMedia.utils.decorators.language import language, languageCB
from AnnieXMedia.utils.inline.stats import (
    build_stats_keyboard,
    build_back_keyboard,
    StatsCallbacks,
)
from config import BANNED_USERS


async def _edit_media_or_reply_with_video(cbq, caption: str, reply_markup):
    media = InputMediaVideo(media=config.STATS_VID_URL, caption=caption)
    try:
        await cbq.edit_message_media(media=media, reply_markup=reply_markup)
    except Exception:
        try:
            await cbq.message.reply_video(
                video=config.STATS_VID_URL, caption=caption, reply_markup=reply_markup
            )
        except Exception:
            await cbq.message.reply_text(text=caption, reply_markup=reply_markup)


async def _safe_edit_caption_or_text(cbq, text: str, reply_markup=None):
    try:
        await cbq.edit_message_caption(caption=text, reply_markup=reply_markup)
    except Exception:
        try:
            await cbq.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
            pass


@app.on_message(filters.command(["stats", "gstats"]) & ~BANNED_USERS)
@language
async def open_stats(client, message: Message, _):
    is_sudo = message.from_user and (message.from_user.id in SUDOERS)
    keyboard = build_stats_keyboard(_, is_sudo)
    try:
        await message.reply_video(
            video=config.STATS_VID_URL,
            caption=_["gstats_2"].format(app.mention),
            reply_markup=keyboard,
        )
    except Exception:
        await message.reply_text(
            text=_["gstats_2"].format(app.mention),
            reply_markup=keyboard,
        )


@app.on_callback_query(filters.regex(f"^{StatsCallbacks.BACK}$") & ~BANNED_USERS)
@languageCB
async def handle_back_to_stats(client, callback_query, _):
    try:
        await callback_query.answer()
    except Exception:
        pass
    is_sudo = callback_query.from_user and (callback_query.from_user.id in SUDOERS)
    keyboard = build_stats_keyboard(_, is_sudo)
    await _safe_edit_caption_or_text(
        callback_query, text=_["gstats_2"].format(app.mention), reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(f"^{StatsCallbacks.SHOW_OVERVIEW}$") & ~BANNED_USERS)
@languageCB
async def handle_show_overview(client, callback_query, _):
    try:
        await callback_query.answer()
    except Exception:
        pass
    back_keyboard = build_back_keyboard(_)
    await _safe_edit_caption_or_text(callback_query, text=_["gstats_1"].format(app.mention))
    served_chats, served_users = await asyncio.gather(
        get_served_chats_count(),
        get_served_users_count(),
    )
    caption = _["gstats_3"].format(
        app.mention,
        len(assistants),
        len(BANNED_USERS),
        served_chats,
        served_users,
        len(ALL_MODULES),
        len(SUDOERS),
        config.AUTO_LEAVING_ASSISTANT,
        config.DURATION_LIMIT_MIN,
    )
    await _edit_media_or_reply_with_video(callback_query, caption, back_keyboard)


def _collect_system_metrics():
    physical_cores = psutil.cpu_count(logical=False)
    total_cores = psutil.cpu_count(logical=True)
    ram_total_gb = f"{round(psutil.virtual_memory().total / (1024.0 ** 3))} ɢʙ"
    try:
        cfreq = psutil.cpu_freq()
        if cfreq and cfreq.current:
            freq_current = cfreq.current
            if freq_current >= 1000:
                cpu_freq = f"{round(freq_current / 1000, 2)}ɢʜᴢ"
            else:
                cpu_freq = f"{round(freq_current, 2)}ᴍʜᴢ"
        else:
            cpu_freq = "ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ"
    except Exception:
        cpu_freq = "ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ"
    try:
        disk = psutil.disk_usage("/")
        disk_total = f"{disk.total / (1024.0 ** 3):.2f}"
        disk_used = f"{disk.used / (1024.0 ** 3):.2f}"
        disk_free = f"{disk.free / (1024.0 ** 3):.2f}"
    except Exception:
        disk_total, disk_used, disk_free = "N/A", "N/A", "N/A"
    return physical_cores, total_cores, ram_total_gb, cpu_freq, disk_total, disk_used, disk_free


@app.on_callback_query(filters.regex(f"^{StatsCallbacks.SHOW_BOT_STATS}$") & ~BANNED_USERS)
@languageCB
async def handle_show_bot_stats(client, callback_query, _):
    if not callback_query.from_user or callback_query.from_user.id not in SUDOERS:
        return await callback_query.answer(_["gstats_4"], show_alert=True)
    back_keyboard = build_back_keyboard(_)
    try:
        await callback_query.answer()
    except Exception:
        pass
    await _safe_edit_caption_or_text(callback_query, text=_["gstats_1"].format(app.mention))
    (
        physical_cores,
        total_cores,
        ram_total_gb,
        cpu_freq,
        disk_total,
        disk_used,
        disk_free,
    ) = await asyncio.to_thread(_collect_system_metrics)
    try:
        db_stats = await mongodb.command("dbstats")
        data_size_mb = f"{db_stats.get('dataSize', 0) / (1024 ** 2):.2f}"
        storage_mb = f"{db_stats.get('storageSize', 0) / (1024 ** 2):.2f}"
        collections = db_stats.get("collections", 0)
        objects = db_stats.get("objects", 0)
    except Exception:
        data_size_mb, storage_mb, collections, objects = "0", "0", 0, 0
    served_chats, served_users, sudoers_list = await asyncio.gather(
        get_served_chats_count(),
        get_served_users_count(),
        get_sudoers(),
    )
    caption = _["gstats_5"].format(
        app.mention,
        len(ALL_MODULES),
        platform.system(),
        ram_total_gb,
        physical_cores,
        total_cores,
        cpu_freq,
        pyver.split()[0],
        pyrover,
        pytgver,
        disk_total,
        disk_used,
        disk_free,
        served_chats,
        served_users,
        len(BANNED_USERS),
        len(sudoers_list),
        data_size_mb,
        storage_mb,
        collections,
        objects,
    )
    await _edit_media_or_reply_with_video(callback_query, caption, back_keyboard)
