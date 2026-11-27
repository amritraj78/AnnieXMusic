# Authored By Certified Coders © 2025
import asyncio
import html
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import MessageDeleteForbidden, RPCError, FloodWait
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.utils.admin_filters import admin_filter

_ALLOWED_PURGE_CHATS = (ChatType.SUPERGROUP, ChatType.FORUM)
_MAX_PURGE_RANGE = 2000


async def _run_purge_range(app: Client, msg: Message, silent: bool = False):
    start_id = msg.reply_to_message.id
    end_id = msg.id
    if start_id >= end_id:
        return await msg.reply("**ʀᴇᴘʟʏ ᴛᴏ ᴀɴ ᴏʟᴅᴇʀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴘᴜʀɢᴇ.**")

    total = end_id - start_id
    if total > _MAX_PURGE_RANGE:
        return await msg.reply(f"**ᴄᴀɴɴᴏᴛ ᴘᴜʀɢᴇ ᴍᴏʀᴇ ᴛʜᴀɴ `{_MAX_PURGE_RANGE}` ᴍᴇssᴀɢᴇs ᴀᴛ ᴏɴᴄᴇ (requested `{total}`).**")

    try:
        for batch_start in range(start_id, end_id, 100):
            plist = list(range(batch_start, min(batch_start + 100, end_id)))
            try:
                await app.delete_messages(chat_id=msg.chat.id, message_ids=plist, revoke=True)
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(min(int(e.value), 60))
                await app.delete_messages(chat_id=msg.chat.id, message_ids=plist, revoke=True)
        try:
            await msg.delete()
        except Exception:
            pass
        if not silent:
            confirm = await app.send_message(chat_id=msg.chat.id, text=f"✅ | **ᴅᴇʟᴇᴛᴇᴅ `{total}` ᴍᴇssᴀɢᴇs.**")
            await asyncio.sleep(3)
            try:
                await confirm.delete()
            except Exception:
                pass
    except MessageDeleteForbidden:
        await msg.reply("**ɪ ᴄᴀɴ'ᴛ ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇs ɪɴ ᴛʜɪs ᴄʜᴀᴛ. ᴍᴀʏ ʙᴇ ᴛᴏᴏ ᴏʟᴅ ᴏʀ ɴᴏ ʀɪɢʜᴛs.**")
    except RPCError as e:
        await msg.reply(f"**ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ:**\n<code>{html.escape(str(e))}</code>")


@app.on_message(filters.command("purge") & admin_filter)
async def purge(app: Client, msg: Message):
    if msg.chat.type not in _ALLOWED_PURGE_CHATS:
        return await msg.reply("**ɪ ᴄᴀɴ'ᴛ ᴘᴜʀɢᴇ ᴍᴇssᴀɢᴇs ɪɴ ᴀ ʙᴀsɪᴄ ɢʀᴏᴜᴘ. ᴘʟᴇᴀsᴇ ᴄᴏɴᴠᴇʀᴛ ɪᴛ ᴛᴏ ᴀ sᴜᴘᴇʀɢʀᴏᴜᴘ.**")

    if not msg.reply_to_message:
        return await msg.reply("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ sᴛᴀʀᴛ ᴘᴜʀɢᴇ!**")

    await _run_purge_range(app, msg, silent=False)


@app.on_message(filters.command("spurge") & admin_filter)
async def spurge(app: Client, msg: Message):
    if msg.chat.type not in _ALLOWED_PURGE_CHATS:
        return await msg.reply("**ɪ ᴄᴀɴ'ᴛ ᴘᴜʀɢᴇ ᴍᴇssᴀɢᴇs ɪɴ ᴀ ʙᴀsɪᴄ ɢʀᴏᴜᴘ. ᴘʟᴇᴀsᴇ ᴄᴏɴᴠᴇʀᴛ ɪᴛ ᴛᴏ ᴀ sᴜᴘᴇʀɢʀᴏᴜᴘ.**")

    if not msg.reply_to_message:
        return await msg.reply("**ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ sᴛᴀʀᴛ ᴘᴜʀɢᴇ!**")

    await _run_purge_range(app, msg, silent=True)


@app.on_message(filters.command("del") & admin_filter)
async def del_msg(app: Client, msg: Message):
    if msg.chat.type not in _ALLOWED_PURGE_CHATS:
        return await msg.reply("**ɪ ᴄᴀɴ'ᴛ ᴘᴜʀɢᴇ ᴍᴇssᴀɢᴇs ɪɴ ᴀ ʙᴀsɪᴄ ɢʀᴏᴜᴘ.**")

    if not msg.reply_to_message:
        return await msg.reply("**ᴡʜᴀᴛ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ?**")

    try:
        await msg.delete()
        await app.delete_messages(chat_id=msg.chat.id, message_ids=msg.reply_to_message.id)
    except FloodWait as e:
        await asyncio.sleep(min(int(e.value), 60))
    except Exception as e:
        await msg.reply(f"**ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴍᴇssᴀɢᴇ:**\n<code>{html.escape(str(e))}</code>")
