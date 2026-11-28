# Authored By Certified Coders © 2025
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait

from AnnieXMedia import app
from AnnieXMedia.core.tasks import spawn_task
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False


_BROADCAST_FLAGS = {"-pin", "-pinloud", "-nobot", "-assistant", "-user"}


def _extract_flags_and_query(raw_text: str) -> tuple[set[str], str]:
    body = raw_text.split(None, 1)[1] if len(raw_text.split(None, 1)) > 1 else ""
    flags = set()
    kept = []
    for tok in body.split():
        if tok in _BROADCAST_FLAGS:
            flags.add(tok)
        else:
            kept.append(tok)
    return flags, " ".join(kept).strip()


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text("⚠️ A broadcast is already in progress. Please wait.")

    msg_text = message.text or message.caption or ""
    flags, query = _extract_flags_and_query(msg_text)
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        if not query:
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    try:
        await message.reply_text(_["broad_1"])

        pin_loud = "-pinloud" in flags
        pin_silent = "-pin" in flags and not pin_loud

        if "-nobot" not in flags:
            sent = 0
            pin = 0
            chats = []
            schats = await get_served_chats()
            for chat in schats:
                chats.append(int(chat["chat_id"]))
            for i in chats:
                try:
                    m = (
                        await app.forward_messages(i, y, x)
                        if message.reply_to_message
                        else await app.send_message(i, text=query)
                    )
                    if pin_loud:
                        try:
                            await m.pin(disable_notification=False)
                            pin += 1
                        except Exception:
                            pass
                    elif pin_silent:
                        try:
                            await m.pin(disable_notification=True)
                            pin += 1
                        except Exception:
                            pass
                    sent += 1
                    await asyncio.sleep(0.2)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        continue
                    await asyncio.sleep(flood_time)
                except Exception:
                    continue
            try:
                await message.reply_text(_["broad_3"].format(sent, pin))
            except Exception:
                pass

        if "-user" in flags:
            susr = 0
            served_users = []
            susers = await get_served_users()
            for user in susers:
                served_users.append(int(user["user_id"]))
            for i in served_users:
                try:
                    m = (
                        await app.forward_messages(i, y, x)
                        if message.reply_to_message
                        else await app.send_message(i, text=query)
                    )
                    susr += 1
                    await asyncio.sleep(0.2)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        continue
                    await asyncio.sleep(flood_time)
                except Exception:
                    pass
            try:
                await message.reply_text(_["broad_4"].format(susr))
            except Exception:
                pass

        if "-assistant" in flags:
            aw = await message.reply_text(_["broad_5"])
            text = _["broad_6"]
            from AnnieXMedia.core.userbot import assistants

            for num in list(assistants):
                sent = 0
                ub = await get_client(num)
                if not ub:
                    continue
                async for dialog in ub.get_dialogs():
                    try:
                        await ub.forward_messages(
                            dialog.chat.id, y, x
                        ) if message.reply_to_message else await ub.send_message(
                            dialog.chat.id, text=query
                        )
                        sent += 1
                        await asyncio.sleep(3)
                    except FloodWait as fw:
                        flood_time = int(fw.value)
                        if flood_time > 200:
                            continue
                        await asyncio.sleep(flood_time)
                    except Exception:
                        continue
                text += _["broad_7"].format(num, sent)
            try:
                await aw.edit_text(text)
            except Exception:
                pass
    finally:
        IS_BROADCASTING = False


async def auto_clean():
    while True:
        try:
            await asyncio.sleep(10)
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id in adminlist:
                    continue
                try:
                    new_admins = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        u = getattr(user, "user", None)
                        if u and getattr(user, "privileges", None) and getattr(user.privileges, 'can_manage_video_chats', False):
                            new_admins.append(u.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        new_admins.append(user_id)
                    adminlist[chat_id] = new_admins
                except Exception:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)


try:
    spawn_task(auto_clean(), name="broadcast_auto_clean")
except RuntimeError:
    pass
