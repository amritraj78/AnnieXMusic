# Authored By Certified Coders © 2025
import asyncio
import html
import os
import shutil
import socket
import sys
from datetime import datetime

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pyrogram import filters
from pyrogram.types import LinkPreviewOptions

import config
from AnnieXMedia import app
from AnnieXMedia.misc import HAPP, SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.pastebin import ANNIEBIN
from AnnieXMedia.utils.security import redact_secrets


async def is_heroku():
    fqdn = await asyncio.to_thread(socket.getfqdn)
    return "heroku" in fqdn


def cleanup_storage():
    folders_to_clean = ["downloads", "raw_files", "cache", "playback"]
    for folder in folders_to_clean:
        if os.path.exists(folder):
            for item in os.listdir(folder):
                item_path = os.path.join(folder, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception:
                    pass
        else:
            os.makedirs(folder, exist_ok=True)


def _git_collect_updates(branch: str):
    repo = Repo()
    remote_url = redact_secrets(repo.remotes.origin.url).split(".git")[0]
    commits = list(repo.iter_commits(f"HEAD..origin/{branch}"))
    return remote_url, commits


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & SUDOERS)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except Exception:
        await message.reply_text(_["server_1"])


@app.on_message(filters.command(["update", "gitpull"]) & SUDOERS)
@language
async def update_(client, message, _):
    if await is_heroku() and HAPP is None:
        return await message.reply_text(_["server_2"])

    response = await message.reply_text(_["server_3"])
    try:
        await asyncio.to_thread(Repo)
    except GitCommandError:
        return await response.edit(_["server_4"])
    except InvalidGitRepositoryError:
        return await response.edit(_["server_5"])

    fetch_proc = await asyncio.create_subprocess_exec(
        "git", "fetch", "origin", config.UPSTREAM_BRANCH,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await fetch_proc.communicate()

    repo_url, commits = await asyncio.to_thread(_git_collect_updates, config.UPSTREAM_BRANCH)
    if not commits:
        return await response.edit(_["server_6"])

    ordinal = lambda num: "%d%s" % (
        num,
        "tsnrhtdd"[(num // 10 % 10 != 1) * (num % 10 < 4) * num % 10 :: 4],
    )
    updates = ""
    safe_repo = html.escape(repo_url, quote=True)
    for info in commits:
        dt = datetime.fromtimestamp(info.committed_date)
        summary = html.escape(str(info.summary))
        author = html.escape(str(info.author))
        updates += (
            f"<b>\u2793 #{info.count()}: <a href=\"{safe_repo}/commit/{info}\">{summary}</a> ʙʏ -> {author}</b>\n"
            f"\t\t\t\t<b>\u279e ᴄᴏᴍᴍɪᴛᴇᴅ ᴏɴ :</b> {ordinal(int(dt.strftime('%d')))} "
            f"{dt.strftime('%b')}, {dt.strftime('%Y')}\n\n"
        )

    _update_response_ = (
        "<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n"
        "\u2793 ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n"
        "<b><u>ᴜᴩᴅᴀᴛᴇs:</u></b>\n\n"
    )
    _final_updates_ = _update_response_ + updates

    if len(_final_updates_) > 4096:
        url = await ANNIEBIN(updates)
        nrs = await response.edit(
            f"<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n"
            f"\u2793 ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n"
            f"<u><b>ᴜᴩᴅᴀᴛᴇs :</b></u>\n\n<a href={url}>ᴄʜᴇᴄᴋ ᴜᴩᴅᴀᴛᴇs</a>"
        )
    else:
        nrs = await response.edit(
            _final_updates_, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    pull_proc = await asyncio.create_subprocess_exec(
        "git", "pull",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await pull_proc.communicate()

    try:
        served_chats = await get_active_chats()
        for x in served_chats:
            try:
                await app.send_message(chat_id=int(x), text=_["server_8"].format(app.mention))
                await remove_active_chat(x)
                await remove_active_video_chat(x)
            except Exception:
                pass
        await response.edit(f"{nrs.text}\n\n{_['server_7']}")
    except Exception:
        pass

    await asyncio.to_thread(cleanup_storage)

    if await is_heroku() and HAPP is not None:
        try:
            await asyncio.to_thread(HAPP.restart)
            return
        except Exception as err:
            await response.edit(f"{nrs.text}\n\n{_['server_9']}")
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=_["server_10"].format(html.escape(redact_secrets(str(err)))),
            )
    os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])


@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    response = await message.reply_text("ʀᴇsᴛᴀʀᴛɪɴɢ...")
    ac_chats = await get_active_chats()
    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
        except Exception:
            pass

    await asyncio.to_thread(cleanup_storage)

    await response.edit_text(
        "» ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴜɴᴛɪʟ ᴛʜᴇ ʙᴏᴛ sᴛᴀʀᴛs..."
    )

    os.execv(sys.executable, [sys.executable, "-m", "AnnieXMedia"])
