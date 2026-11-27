# Authored By Certified Coders © 2025
import html
from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.mongo.pretenderdb import (
    impo_off, impo_on, check_pretender,
    add_userdata, get_userdata,
)
from AnnieXMedia.utils.admin_filters import admin_filter

_pretender_cache: dict[int, bool] = {}


def _clean_field(val: str | None, fallback: str = "") -> str:
    if not val:
        return fallback
    safe = html.escape(val.strip()[:128])
    return safe.replace("*", "").replace("_", "").replace("`", "'").replace("[", "(").replace("]", ")")


async def _is_pretender_enabled(chat_id: int) -> bool:
    if chat_id in _pretender_cache:
        return _pretender_cache[chat_id]
    enabled = await check_pretender(chat_id)
    if len(_pretender_cache) > 2048:
        _pretender_cache.clear()
    _pretender_cache[chat_id] = enabled
    return enabled


@app.on_message(filters.group & ~filters.bot & ~filters.via_bot, group=69)
async def chk_usr(_, message: Message):
    if not message.from_user or message.sender_chat or not await _is_pretender_enabled(message.chat.id):
        return

    user = message.from_user
    usernamebefore, first_name, lastname_before = await get_userdata(user.id)
    if usernamebefore is None and first_name is None and lastname_before is None:
        return await add_userdata(user.id, user.username, user.first_name, user.last_name)

    changed = (
        usernamebefore != user.username
        or first_name != user.first_name
        or lastname_before != user.last_name
    )
    if not changed:
        return

    await add_userdata(user.id, user.username, user.first_name, user.last_name)

    msg = f"""
**🔓 ᴘʀᴇᴛᴇɴᴅᴇʀ ᴅᴇᴛᴇᴄᴛᴇᴅ 🔓**
━━━━━━━━━━━━━━━  
**🍊 ɴᴀᴍᴇ** : {user.mention}
**🍅 ᴜsᴇʀ ɪᴅ** : `{user.id}`
━━━━━━━━━━━━━━━  \n
"""
    if usernamebefore != user.username:
        ub = _clean_field(f"@{usernamebefore}" if usernamebefore else None, "NO USERNAME")
        ua = _clean_field(f"@{user.username}" if user.username else None, "NO USERNAME")
        msg += f"""
**🐻‍❄️ ᴄʜᴀɴɢᴇᴅ ᴜsᴇʀɴᴀᴍᴇ 🐻‍❄️**
━━━━━━━━━━━━━━━  
**🎭 ғʀᴏᴍ** : {ub}
**🍜 ᴛᴏ** : {ua}
━━━━━━━━━━━━━━━  \n
"""
    if first_name != user.first_name:
        msg += f"""
**🪧 ᴄʜᴀɴɢᴇs ғɪʀsᴛ ɴᴀᴍᴇ 🪧**
━━━━━━━━━━━━━━━  
**🔐 ғʀᴏᴍ** : {_clean_field(first_name, 'NONE')}
**🍓 ᴛᴏ** : {_clean_field(user.first_name, 'NONE')}
━━━━━━━━━━━━━━━  \n
"""
    if lastname_before != user.last_name:
        lb = _clean_field(lastname_before, "NO LAST NAME")
        la = _clean_field(user.last_name, "NO LAST NAME")
        msg += f"""
**🪧 ᴄʜᴀɴɢᴇs ʟᴀsᴛ ɴᴀᴍᴇ 🪧**
━━━━━━━━━━━━━━━  
**🚏ғʀᴏᴍ** : {lb}
**🍕 ᴛᴏ** : {la}
━━━━━━━━━━━━━━━  \n
"""
    try:
        await message.reply_photo("https://telegra.ph/file/58afe55fee5ae99d6901b.jpg", caption=msg[:1024])
    except Exception:
        try:
            await message.reply_text(msg[:4096])
        except Exception:
            pass


@app.on_message(filters.group & filters.command("imposter") & ~filters.bot & ~filters.via_bot & admin_filter)
async def set_mataa(_, message: Message):
    if len(message.command) == 1:
        return await message.reply("ᴅᴇᴛᴇᴄᴛ ᴘʀᴇᴛᴇɴᴅᴇʀ ᴜsᴇʀs **ᴜsᴀɢᴇ:** `/imposter enable|disable`")
    action = message.command[1].lower()
    is_enabled = await check_pretender(message.chat.id)
    chat_title = _clean_field(message.chat.title, "this chat")
    if action in ("enable", "on"):
        if is_enabled:
            await message.reply("**ᴘʀᴇᴛᴇɴᴅᴇʀ ᴍᴏᴅᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.**")
        else:
            await impo_on(message.chat.id)
            _pretender_cache[message.chat.id] = True
            await message.reply(f"**sᴜᴄᴄᴇssғᴜʟʟʏ ᴇɴᴀʙʟᴇᴅ ᴘʀᴇᴛᴇɴᴅᴇʀ ᴍᴏᴅᴇ ғᴏʀ** {chat_title}")
    elif action in ("disable", "off"):
        if not is_enabled:
            await message.reply("**ᴘʀᴇᴛᴇɴᴅᴇʀ ᴍᴏᴅᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.**")
        else:
            await impo_off(message.chat.id)
            _pretender_cache[message.chat.id] = False
            await message.reply(f"**sᴜᴄᴄᴇssғᴜʟʟʏ ᴅɪsᴀʙʟᴇᴅ ᴘʀᴇᴛᴇɴᴅᴇʀ ᴍᴏᴅᴇ ғᴏʀ** {chat_title}")
    else:
        await message.reply("**ᴅᴇᴛᴇᴄᴛ ᴘʀᴇᴛᴇɴᴅᴇʀ ᴜsᴇʀs ᴜsᴀɢᴇ : /imposter enable|disable**")
