# Authored By Certified Coders © 2025
import re
import aiohttp
from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.downloader import get_http_session


async def get_waifu_data(tag: str):
    try:
        session = await get_http_session()
        async with session.get(
            "https://api.waifu.im/search",
            params={"included_tags": tag, "height": ">=2000"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        LOGGER(__name__).debug(f"[Waifu Error] {e}")
    return None


@app.on_message(filters.command("waifu"))
async def waifu_command_handler(_, message: Message):
    try:
        args = (message.text or message.caption or "").split(maxsplit=1)
        tag = args[1].strip().lower() if len(args) > 1 else "maid"
        if not re.match(r"^[a-z0-9_-]{1,32}$", tag):
            return await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴡᴀɪꜰᴜ ᴛᴀɢ.")

        waifu_data = await get_waifu_data(tag)

        if waifu_data and isinstance(waifu_data.get("images"), list) and waifu_data["images"]:
            image = waifu_data["images"][0]
            img_url = image.get("url")
            if not img_url:
                return await message.reply_text("❌ ɴᴏ ᴡᴀɪꜰᴜꜱ ꜰᴏᴜɴᴅ ᴡɪᴛʜ ᴛʜᴀᴛ ᴛᴀɢ.")
            try:
                await message.reply_photo(
                    photo=img_url,
                    caption=f"🌸 ʜᴇʀᴇ'ꜱ ʏᴏᴜʀ ᴡᴀɪꜰᴜ ({tag})"
                )
            except Exception:
                await message.reply_text(f"🌸 ʜᴇʀᴇ'ꜱ ʏᴏᴜʀ ᴡᴀɪꜰᴜ ({tag}): {img_url}")
        else:
            await message.reply_text("❌ ɴᴏ ᴡᴀɪꜰᴜꜱ ꜰᴏᴜɴᴅ ᴡɪᴛʜ ᴛʜᴀᴛ ᴛᴀɢ.")

    except Exception as e:
        safe_err = str(e).replace("`", "'")
        await message.reply_text(f"⚠️ ᴇʀʀᴏʀ: `{safe_err}`")
