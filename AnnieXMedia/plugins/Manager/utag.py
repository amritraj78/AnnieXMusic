# Authored By Certified Coders © 2025
import asyncio
import html
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import admin_filter

spam_chats: set[int] = set()
_utag_tasks: dict[int, asyncio.Task] = {}


async def _run_utag(client: Client, message: Message, replied, text: str):
    chat_id = message.chat.id
    usernum, usertxt, total_tagged = 0, "", 0

    try:
        async for member in client.get_chat_members(chat_id):
            if chat_id not in spam_chats:
                break

            if not member.user or member.user.is_bot:
                continue

            usernum += 1
            total_tagged += 1
            safe_name = html.escape((member.user.first_name or "User").replace("[", "").replace("]", ""))
            usertxt += f"⊚ [{safe_name}](tg://user?id={member.user.id})\n"

            if usernum == 5:
                try:
                    target = replied or message
                    await target.reply_text(f"{text}\n{usertxt}\n📢 ᴛᴀɢɢɪɴɢ {total_tagged} ᴜsᴇʀs ᴅᴏɴᴇ...")
                except FloodWait as e:
                    await asyncio.sleep(min(int(e.value), 60))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

                await asyncio.sleep(3)
                usernum, usertxt = 0, ""

        if usertxt and chat_id in spam_chats:
            try:
                target = replied or message
                await target.reply_text(f"{text}\n{usertxt}\n📢 ᴛᴀɢɢɪɴɢ {total_tagged} ᴜsᴇʀs ᴅᴏɴᴇ...")
            except FloodWait as e:
                await asyncio.sleep(min(int(e.value), 60))
            except Exception:
                pass

        try:
            await message.reply(f"✅ **ᴛᴀɢɢɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇᴅ. ᴛᴏᴛᴀʟ:** `{total_tagged}` **ᴜsᴇʀs.**")
        except Exception:
            pass
    except asyncio.CancelledError:
        pass
    finally:
        spam_chats.discard(chat_id)
        _utag_tasks.pop(chat_id, None)


@app.on_message(filters.command(["utag", "all", "mention"]) & filters.group & admin_filter)
async def tag_all_users(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in spam_chats:
        return await message.reply("⚠️ **ᴀ ᴛᴀɢɢɪɴɢ sᴇssɪᴏɴ ɪs ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ. ᴜsᴇ /cancel ᴏʀ /ustop ᴛᴏ sᴛᴏᴘ ɪᴛ.**")

    replied = message.reply_to_message
    parts = (message.text or message.caption or "").split(None, 1)
    text = parts[1] if len(parts) > 1 else ""

    if not replied and not text:
        return await message.reply("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ ɢɪᴠᴇ sᴏᴍᴇ ᴛᴇxᴛ ᴛᴏ ᴛᴀɢ ᴀʟʟ.**")

    spam_chats.add(chat_id)
    _utag_tasks[chat_id] = asyncio.create_task(_run_utag(client, message, replied, text))


@app.on_message(filters.command(["cancel", "ustop"]) & filters.group)
async def cancel_spam(client: Client, message: Message):
    chat_id = message.chat.id

    if chat_id not in spam_chats:
        return await message.reply("**ɪ'ᴍ ɴᴏᴛ ᴛᴀɢɢɪɴɢ ᴀɴʏᴏɴᴇ ʀɪɢʜᴛ ɴᴏᴡ.**")

    if not message.from_user:
        if message.sender_chat and message.sender_chat.id == chat_id:
            spam_chats.discard(chat_id)
            task = _utag_tasks.get(chat_id)
            if task and not task.done():
                task.cancel()
            return await message.reply("**🚫 ᴛᴀɢɢɪɴɢ ᴄᴀɴᴄᴇʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.**")
        return await message.reply("**ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴄᴀɴᴄᴇʟ ᴛᴀɢɢɪɴɢ.**")

    try:
        member = await client.get_chat_member(chat_id, message.from_user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return await message.reply("**ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴄᴀɴᴄᴇʟ ᴛᴀɢɢɪɴɢ.**")
    except UserNotParticipant:
        return await message.reply("**ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀ ᴘᴀʀᴛɪᴄɪᴘᴀɴᴛ ᴏғ ᴛʜɪs ᴄʜᴀᴛ.**")
    except Exception:
        return await message.reply("**ᴇʀʀᴏʀ ᴄʜᴇᴄᴋɪɴɢ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs.**")

    spam_chats.discard(chat_id)
    task = _utag_tasks.get(chat_id)
    if task and not task.done():
        task.cancel()
    return await message.reply("**🚫 ᴛᴀɢɢɪɴɢ ᴄᴀɴᴄᴇʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.**")
