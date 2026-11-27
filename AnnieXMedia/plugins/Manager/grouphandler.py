# Authored By Certified Coders © 2025
import html
from pyrogram import filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import admin_filter

# ------------------- Utility Functions ------------------- #

def is_group(message: Message) -> bool:
    return bool(
        message.chat
        and message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.FORUM)
    )


def _safe_err(err: Exception) -> str:
    return html.escape(str(err).replace("`", "'"))

async def has_permission(message: Message, permission: str) -> bool:
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if not message.from_user:
        return False
    try:
        member = await app.get_chat_member(message.chat.id, message.from_user.id)
        return bool(
            getattr(getattr(member, "privileges", None), permission, False)
            or member.status in (ChatMemberStatus.OWNER, "creator")
        )
    except Exception:
        return False

def admin_mention(message: Message) -> str:
    if message.from_user:
        return message.from_user.mention
    if message.sender_chat:
        return html.escape(message.sender_chat.title or "Admin")
    return "Admin"

def _view_btn(msg: Message):
    try:
        return InlineKeyboardMarkup([[InlineKeyboardButton("📝 ᴠɪᴇᴡ ᴍᴇssᴀɢᴇ", url=msg.link)]])
    except Exception:
        return None

# ------------------- Pin Message ------------------- #

@app.on_message(filters.command("pin") & admin_filter)
async def pin(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")

    if not message.reply_to_message:
        return await message.reply_text("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘɪɴ ɪᴛ!**")

    if not await has_permission(message, "can_pin_messages"):
        return await message.reply_text("**ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴘɪɴ ᴍᴇssᴀɢᴇs.**")

    try:
        await message.reply_to_message.pin()
        chat_title = html.escape(message.chat.title or "Group")
        await message.reply_text(
            f"**sᴜᴄᴄᴇssғᴜʟʟʏ ᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇ!**\n\n**ᴄʜᴀᴛ:** {chat_title}\n**ᴀᴅᴍɪɴ:** {admin_mention(message)}",
            reply_markup=_view_btn(message.reply_to_message)
        )
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ ᴘɪɴ ᴍᴇssᴀɢᴇ:**\n`{_safe_err(e)}`")

# ------------------- Unpin Message ------------------- #

@app.on_message(filters.command("unpin") & admin_filter)
async def unpin(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")

    if not message.reply_to_message:
        return await message.reply_text("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴜɴᴘɪɴ ɪᴛ!**")

    if not await has_permission(message, "can_pin_messages"):
        return await message.reply_text("**ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜɴᴘɪɴ ᴍᴇssᴀɢᴇs.**")

    try:
        await message.reply_to_message.unpin()
        chat_title = html.escape(message.chat.title or "Group")
        await message.reply_text(
            f"**sᴜᴄᴄᴇssғᴜʟʟʏ ᴜɴᴘɪɴɴᴇᴅ ᴍᴇssᴀɢᴇ!**\n\n**ᴄʜᴀᴛ:** {chat_title}\n**ᴀᴅᴍɪɴ:** {admin_mention(message)}",
            reply_markup=_view_btn(message.reply_to_message)
        )
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ ᴜɴᴘɪɴ ᴍᴇssᴀɢᴇ:**\n`{_safe_err(e)}`")

# ------------------- Set / Remove Photo, Title, Description ------------------- #

@app.on_message(filters.command("setphoto") & admin_filter)
async def set_photo(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")
    if not message.reply_to_message:
        return await message.reply_text("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴏʀ ᴅᴏᴄᴜᴍᴇɴᴛ.**")
    if not await has_permission(message, "can_change_info"):
        return await message.reply_text("**ʏᴏᴜ ʟᴀᴄᴋ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ɪɴғᴏ.**")

    target = message.reply_to_message
    file_id = None

    if getattr(target, "photo", None):
        file_id = target.photo.file_id
    elif getattr(target, "document", None) and getattr(target.document, "mime_type", ""):
        if target.document.mime_type.startswith("image/"):
            file_id = target.document.file_id

    if not file_id:
        return await message.reply_text("**ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴀɴ ɪᴍᴀɢᴇ (ᴘʜᴏᴛᴏ ᴏʀ ɪᴍᴀɢᴇ ᴅᴏᴄᴜᴍᴇɴᴛ).**")

    try:
        await app.set_chat_photo(chat_id=message.chat.id, photo=file_id)
        await message.reply_text(f"**ɢʀᴏᴜᴘ ᴘʜᴏᴛᴏ ᴜᴘᴅᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**\nʙʏ {admin_mention(message)}")
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ sᴇᴛ ᴘʜᴏᴛᴏ:**\n`{_safe_err(e)}`")

@app.on_message(filters.command("removephoto") & admin_filter)
async def remove_photo(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")
    if not await has_permission(message, "can_change_info"):
        return await message.reply_text("**ʏᴏᴜ ʟᴀᴄᴋ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ɪɴғᴏ.**")
    try:
        await app.delete_chat_photo(message.chat.id)
        await message.reply_text(f"**ɢʀᴏᴜᴘ ᴘʜᴏᴛᴏ ʀᴇᴍᴏᴠᴇᴅ!**\nʙʏ {admin_mention(message)}")
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴘʜᴏᴛᴏ:**\n`{_safe_err(e)}`")

@app.on_message(filters.command("settitle") & admin_filter)
async def set_title(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")
    if not await has_permission(message, "can_change_info"):
        return await message.reply_text("**ʏᴏᴜ ʟᴀᴄᴋ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ɪɴғᴏ.**")

    title = None
    if len(message.command) > 1:
        parts = (message.text or message.caption or "").split(None, 1)
        title = parts[1].strip() if len(parts) > 1 else None
    elif message.reply_to_message and getattr(message.reply_to_message, "text", None):
        title = message.reply_to_message.text.strip()

    if not title:
        return await message.reply_text("**ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴇᴡ ᴛɪᴛʟᴇ.**")

    try:
        await message.chat.set_title(title)
        await message.reply_text(f"**ɢʀᴏᴜᴘ ɴᴀᴍᴇ ᴄʜᴀɴɢᴇᴅ ᴛᴏ:** {html.escape(title)}\nʙʏ {admin_mention(message)}")
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ sᴇᴛ ᴛɪᴛʟᴇ:**\n`{_safe_err(e)}`")


@app.on_message(filters.command(["setdescription", "setdiscription"]) & admin_filter)
async def set_description(_, message: Message):
    if not is_group(message):
        return await message.reply_text("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!**")
    if not await has_permission(message, "can_change_info"):
        return await message.reply_text("**ʏᴏᴜ ʟᴀᴄᴋ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ɪɴғᴏ.**")

    desc = None
    if len(message.command) > 1:
        parts = (message.text or message.caption or "").split(None, 1)
        desc = parts[1].strip() if len(parts) > 1 else None
    elif message.reply_to_message and getattr(message.reply_to_message, "text", None):
        desc = message.reply_to_message.text.strip()

    if not desc:
        return await message.reply_text("**ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴇᴡ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ.**")

    try:
        await message.chat.set_description(desc)
        await message.reply_text(f"**ɢʀᴏᴜᴘ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ᴜᴘᴅᴀᴛᴇᴅ!**\nʙʏ {admin_mention(message)}")
    except Exception as e:
        await message.reply_text(f"**ғᴀɪʟᴇᴅ ᴛᴏ sᴇᴛ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:**\n`{_safe_err(e)}`")
