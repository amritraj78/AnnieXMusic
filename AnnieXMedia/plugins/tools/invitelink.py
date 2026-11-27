# Authored By Certified Coders © 2025
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChannelInvalid, ChannelPrivate
from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.admin_filters import admin_filter


def _write_group_file(file_path: str, group_data: dict) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        for key, value in group_data.items():
            file.write(f"{key}: {value}\n")


def _cleanup_file(file_path: str | None) -> None:
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass


@app.on_message(filters.command("givelink") & filters.group & admin_filter)
async def give_link_command(client: Client, message: Message):
    try:
        link = await app.export_chat_invite_link(message.chat.id)
        title = (message.chat.title or "this chat").replace("`", "'")
        await message.reply_text(
            f"🔗 **ɪɴᴠɪᴛᴇ ʟɪɴᴋ ғᴏʀ** `{title}`:\n{link}"
        )
    except Exception as e:
        safe_err = str(e).replace("`", "'")
        await message.reply_text(f"❌ ᴇʀʀᴏʀ ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ:\n`{safe_err}`")


@app.on_message(filters.command(["link", "invitelink"], prefixes=["/", "!", ".", "#", "?"]) & SUDOERS)
async def link_command_handler(client: Client, message: Message):
    if len(message.command) != 2:
        return await message.reply("**ᴜsᴀɢᴇ:** `/link <group_id>`")

    file_name = None

    try:
        cid = int(message.command[1])
        file_name = f"cache/group_info_{cid}_{message.id}.txt"
        chat = await client.get_chat(cid)
        if not chat:
            return await message.reply("⚠️ **ᴄᴏᴜʟᴅ ɴᴏᴛ ғᴇᴛᴄʜ ɢʀᴏᴜᴘ ɪɴғᴏ.**")

        try:
            invite_link = await client.export_chat_invite_link(chat.id)
        except (ChannelInvalid, ChannelPrivate):
            return await message.reply("🚫 **ɪ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀᴄᴄᴇss ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.**")
        except FloodWait as e:
            return await message.reply(f"⏳ ʀᴀᴛᴇ ʟɪᴍɪᴛ: ᴡᴀɪᴛ `{e.value}` seconds.")

        group_data = {
            "id": chat.id,
            "type": str(chat.type),
            "title": chat.title,
            "members_count": chat.members_count,
            "description": chat.description,
            "invite_link": invite_link,
            "is_verified": chat.is_verified,
            "is_restricted": chat.is_restricted,
            "is_creator": chat.is_creator,
            "is_scam": chat.is_scam,
            "is_fake": chat.is_fake,
            "dc_id": chat.dc_id,
            "has_protected_content": chat.has_protected_content,
        }

        await asyncio.to_thread(_write_group_file, file_name, group_data)

        safe_title = (chat.title or "Unknown").replace("`", "'")
        caption = (
            f"📂 **ɢʀᴏᴜᴘ ɪɴғᴏ ꜰᴏʀ** `{safe_title}`\n"
            f"📌 **sᴄʀᴀᴘᴇᴅ ʙʏ:** @{app.username}"
        )[:1024]
        await client.send_document(
            chat_id=message.chat.id,
            document=file_name,
            caption=caption,
        )

    except ValueError:
        await message.reply("❌ **ɪɴᴠᴀʟɪᴅ ɢʀᴏᴜᴘ ɪᴅ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɢʀᴏᴜᴘ ɪᴅ.**")
    except Exception as e:
        safe_err = str(e).replace("`", "'")
        await message.reply_text(f"❌ ᴇʀʀᴏʀ:\n`{safe_err}`")

    finally:
        await asyncio.to_thread(_cleanup_file, file_name)
