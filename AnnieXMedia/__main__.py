# Authored By Certified Coders © 2025
import asyncio
import contextlib
import importlib
import sys

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AnnieXMedia import Carbon, LOGGER, app, userbot
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.core.dir import prune_storage_cache
from AnnieXMedia.core.mongo import ensure_indexes
from AnnieXMedia.core.self_heal import start_self_heal, stop_self_heal
from AnnieXMedia.core.server import start_web_server, stop_web_server
from AnnieXMedia.misc import sudo
from AnnieXMedia.plugins import ALL_MODULES
from AnnieXMedia.utils.database import get_banned_users, get_gbanned
from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies
from AnnieXMedia.utils.downloader import close_http_session
from config import BANNED_USERS


async def _periodic_storage_cleanup(interval_seconds: int = 1800):
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(prune_storage_cache)
        except Exception:
            pass


async def init():
    # Start healthcheck & Mini App web server for Koyeb / Render / PaaS deployment
    await start_web_server()

    if not config.BOT_TOKEN or not str(config.BOT_TOKEN).strip():
        LOGGER(__name__).error("BOT_TOKEN is missing! Set BOT_TOKEN in environment variables.")
        await stop_web_server()
        sys.exit(1)

    await ensure_indexes()
    await asyncio.to_thread(prune_storage_cache, 3600)

    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ...")
        await stop_web_server()
        sys.exit(1)

    try:
        await fetch_and_store_cookies()
        LOGGER("AnnieXMedia").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"⚠️ᴄᴏᴏᴋɪᴇ ᴇʀʀᴏʀ: {e}")

    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"Failed to preload banned users: {e}")

    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("AnnieXMedia.plugins" + all_module)

    LOGGER("AnnieXMedia.plugins").info("ᴀɴɴɪᴇ's ᴍᴏᴅᴜʟᴇs ʟᴏᴀᴅᴇᴅ...")

    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call("http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4")
    except NoActiveGroupCall:
        LOGGER("AnnieXMedia").warning(
            "Voice chat in LOGGER_ID is not active. Group calls will be joined on-demand."
        )
    except Exception as e:
        LOGGER("AnnieXMedia").warning(f"Initial logger call test skipped: {e}")

    await StreamController.decorators()
    start_self_heal()
    cleanup_task = asyncio.create_task(_periodic_storage_cleanup())
    LOGGER("AnnieXMedia").info(
        "\x41\x6e\x6e\x69\x65\x20\x4d\x75\x73\x69\x63\x20\x52\x6f\x62\x6f\x74\x20\x53\x74\x61\x72\x74\x65\x64\x20\x53\x75\x63\x63\x65\x73\x73\x66\x75\x6c\x6c\x79\x2e\x2e\x2e"
    )
    try:
        await idle()
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await cleanup_task
        await stop_self_heal()
        for step in (
            StreamController.stop,
            app.stop,
            userbot.stop,
            Carbon.close,
            close_http_session,
            stop_web_server,
        ):
            with contextlib.suppress(Exception):
                await step()
        LOGGER("AnnieXMedia").info("sᴛᴏᴘᴘɪɴɢ ᴀɴɴɪᴇ ᴍᴜsɪᴄ ʙᴏᴛ ...")


if __name__ == "__main__":
    asyncio.run(init())
