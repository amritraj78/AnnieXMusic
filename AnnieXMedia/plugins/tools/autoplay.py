# Authored By Certified Coders © 2025
"""Smart Autoplay Radio toggle and Self-Healing / Cache telemetry commands."""
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.core.self_heal import get_health_snapshot, run_heal_cycle
from AnnieXMedia.core.track_cache import stats as cache_stats, track_cachedb
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import autoplay_off, autoplay_on, is_autoplay
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(filters.command(["autoplay", "radio"]) & filters.group & ~BANNED_USERS)
@language
async def cmd_autoplay(_, message: Message, _lang):
    """Toggle Smart Autoplay Radio on/off for the current group."""
    uid = message.from_user.id if message.from_user else 0
    if not uid:
        return await message.reply_text(_lang["general_3"])

    if uid not in SUDOERS:
        member = await app.get_chat_member(message.chat.id, uid)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply_text(_lang["admin_14"], reply_markup=close_markup(_lang))

    arg = message.command[1].lower() if len(message.command or []) > 1 else ""
    current = await is_autoplay(message.chat.id)
    if arg in ("on", "enable", "1", "yes"):
        await autoplay_on(message.chat.id)
        new_state = True
    elif arg in ("off", "disable", "0", "no"):
        await autoplay_off(message.chat.id)
        new_state = False
    else:
        if current:
            await autoplay_off(message.chat.id)
            new_state = False
        else:
            await autoplay_on(message.chat.id)
            new_state = True

    status_lbl = "✅ **Enabled**" if new_state else "⛔ **Disabled**"
    await message.reply_text(
        f"📻 **Smart Autoplay Radio:** {status_lbl}\n\n"
        f"{'When the queue ends, similar songs will play automatically.' if new_state else 'Bot will leave the Voice Chat after the queue finishes.'}",
        reply_markup=close_markup(_lang),
    )


@app.on_message(filters.command(["selfheal", "heal", "cachestats"]) & SUDOERS)
async def cmd_selfheal(_, message: Message):
    """Display live Self-Healing Watchdog metrics and Telegram Track Cache stats (trigger check if `now`)."""
    arg = message.command[1].lower() if len(message.command or []) > 1 else ""
    if arg in ("now", "run", "fix"):
        await run_heal_cycle()

    snap = get_health_snapshot()
    try:
        cached_total = await track_cachedb.count_documents({})
    except Exception:
        cached_total = 0

    await message.reply_text(
        "🛡️ **AnnieXMusic Self-Heal & Cache Telemetry**\n\n"
        f"• **Bot Connected:** `{'Yes' if snap['bot_connected'] else 'No'}`\n"
        f"• **MongoDB Healthy:** `{'Yes' if snap['db_ok'] else 'No'}`\n"
        f"• **Assistants Online:** `{snap['assistants_online']}`\n"
        f"• **Keep-Alive Ping OK:** `{'Yes' if snap['last_keepalive_ok'] else 'No'}`\n"
        f"• **Auto-Recoveries:** `{snap['recoveries']}` "
        f"(Ghost: `{snap['ghost_calls_healed']}`, Stalled: `{snap['stalled_calls_healed']}`)\n"
        f"• **Handled Async Errors:** `{snap['unhandled_errors']}`\n\n"
        "💾 **Telegram Track Cache (Sub-1s Play)**\n"
        f"• **Cached Mongo Tracks:** `{cached_total}`\n"
        f"• **Telegram CDN Hits:** `{cache_stats['tg_hits']}`\n"
        f"• **Local Disk Hits:** `{cache_stats['disk_hits']}`\n"
        f"• **Background Uploads:** `{cache_stats['uploads']}`\n\n"
        "_Tip: Run `/selfheal now` to force an immediate recovery cycle._",
    )
