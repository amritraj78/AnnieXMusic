# Authored By Certified Coders © 2025
import asyncio
import time
from typing import Dict, Tuple

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteHashExpired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions

from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string
from AnnieXMedia import YouTube, app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from AnnieXMedia.utils.inline import botplaylist_markup

# Cache for invite links per chat and lightweight per-user cooldown
links = {}
_play_cooldown: Dict[Tuple[int, int], float] = {}
_bg_tasks: set[asyncio.Task] = set()
_PLAY_COOLDOWN_SEC = 2.5


async def _delete_after(msg, delay: float = 4.0) -> None:
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


def PlayWrapper(command):
    async def wrapper(client, message):
        language = await get_lang(message.chat.id)
        _ = get_string(language)

        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        if await is_maintenance() is False:
            if not message.from_user or message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )

        if message.from_user and message.from_user.id not in SUDOERS:
            now = time.monotonic()
            key = (message.chat.id, message.from_user.id)
            last_ts = _play_cooldown.get(key, 0.0)
            if now - last_ts < _PLAY_COOLDOWN_SEC:
                warn = await message.reply_text("⏳ Please wait a couple seconds before queueing another track.")
                t = asyncio.create_task(_delete_after(warn, 4.0))
                _bg_tasks.add(t)
                t.add_done_callback(_bg_tasks.discard)
                return
            if len(_play_cooldown) > 2048:
                cutoff = now - 60.0
                for k, v in list(_play_cooldown.items()):
                    if v < cutoff:
                        _play_cooldown.pop(k, None)
            _play_cooldown[key] = now

        try:
            await message.delete()
        except Exception:
            pass

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)

        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                try:
                    return await message.reply_photo(
                        photo=PLAYLIST_IMG_URL,
                        caption=_["play_18"],
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                except Exception:
                    return await message.reply_text(
                        _["play_18"],
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None

        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        if playty != "Everyone":
            uid = message.from_user.id if message.from_user else 0
            if uid not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                elif uid not in admins:
                    return await message.reply_text(_["play_4"])

        cmd_name = message.command[0] if message.command else "play"
        msg_raw = message.text or message.caption or ""
        if cmd_name[0] == "v":
            video = True
        else:
            if "-v" in msg_raw:
                video = True
            else:
                video = True if len(cmd_name) > 1 and cmd_name[1] == "v" else None

        if cmd_name[-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            if not userbot or not getattr(userbot, "id", None):
                return await message.reply_text(_["call_1"])
            try:
                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                except ChatAdminRequired:
                    return await message.reply_text(_["call_1"])

                if member.status in (
                    ChatMemberStatus.BANNED,
                    ChatMemberStatus.RESTRICTED,
                ):
                    return await message.reply_text(
                        _["call_2"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        text="๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏",
                                        callback_data="unban_assistant",
                                    )
                                ]
                            ]
                        ),
                    )
            except UserNotParticipant:
                try:
                    target_chat = await app.get_chat(chat_id)
                except Exception:
                    target_chat = None
                if target_chat and getattr(target_chat, "username", None):
                    invitelink = target_chat.username
                    try:
                        await userbot.resolve_peer(invitelink)
                    except Exception:
                        pass
                elif chat_id == message.chat.id and message.chat.username:
                    invitelink = message.chat.username
                    try:
                        await userbot.resolve_peer(invitelink)
                    except Exception:
                        pass
                else:
                    try:
                        invitelink = await app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        return await message.reply_text(_["call_1"])
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )

                if invitelink and invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )

                myu = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteHashExpired:
                    if chat_id in links:
                        del links[chat_id]
                    try:
                        invitelink = await app.export_chat_invite_link(chat_id)
                    except ChatAdminRequired:
                        try:
                            await myu.delete()
                        except Exception:
                            pass
                        return await message.reply_text(_["call_1"])
                    except Exception as e:
                        try:
                            await myu.delete()
                        except Exception:
                            pass
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    if invitelink and invitelink.startswith("https://t.me/+"):
                        invitelink = invitelink.replace(
                            "https://t.me/+", "https://t.me/joinchat/"
                        )
                    links[chat_id] = invitelink
                    try:
                        await userbot.join_chat(invitelink)
                    except UserAlreadyParticipant:
                        pass
                    except Exception as e:
                        try:
                            await myu.delete()
                        except Exception:
                            pass
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    try:
                        await myu.edit(_["call_5"].format(app.mention))
                    except Exception:
                        pass
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    try:
                        await myu.delete()
                    except Exception:
                        pass
                    return await message.reply_text(
                        _["call_3"].format(app.mention, type(e).__name__)
                    )

                if invitelink:
                    if len(links) > 2048:
                        links.clear()
                    links[chat_id] = invitelink

                try:
                    await myu.delete()
                except Exception:
                    pass

                try:
                    await userbot.resolve_peer(chat_id)
                except Exception:
                    pass

        return await command(
            client, message, _, chat_id, video, channel, playmode, url, fplay
        )

    return wrapper
