# Authored By Certified Coders © 2025
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError
from pyrogram import errors, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.core.dir import COUPLE_DIR
from AnnieXMedia.mongo.couples_db import get_couple, save_couple


ASSETS = Path("AnnieXMedia/assets")
FALLBACK = ASSETS / "upic.png"
OUT_DIR = Path(COUPLE_DIR)
_COUPLE_LOCKS: dict[int, asyncio.Lock] = {}


def _lock_for_chat(chat_id: int) -> asyncio.Lock:
    if len(_COUPLE_LOCKS) > 512:
        for k, lk in list(_COUPLE_LOCKS.items()):
            if not lk.locked():
                _COUPLE_LOCKS.pop(k, None)
    return _COUPLE_LOCKS.setdefault(chat_id, asyncio.Lock())


def today() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def tomorrow() -> str:
    return (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")


def circular(path: str | Path) -> Image.Image:
    try:
        with Image.open(path) as raw:
            img = raw.convert("RGBA").resize((486, 486))
    except (FileNotFoundError, UnidentifiedImageError):
        with Image.open(FALLBACK) as raw:
            img = raw.convert("RGBA").resize((486, 486))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + img.size, fill=255)
    img.putalpha(mask)
    return img


async def safe_get_user(uid: int):
    try:
        return await app.get_users(uid)
    except errors.PeerIdInvalid:
        return None


async def safe_photo(uid: int, name: str) -> Path:
    try:
        chat = await app.get_chat(uid)
        if chat.photo and chat.photo.big_file_id:
            path = await app.download_media(chat.photo.big_file_id, file_name=OUT_DIR / name)
            return Path(path) if path else FALLBACK
    except Exception:
        pass
    return FALLBACK


def _compose_couple_image(p1: Path, p2: Path, out_path: Path):
    with Image.open(ASSETS / "annie/couple.png") as raw_base:
        base = raw_base.convert("RGBA")
    a1 = circular(p1)
    a2 = circular(p2)
    base.paste(a1, (410, 500), a1)
    base.paste(a2, (1395, 500), a2)
    base.save(out_path)
    base.close()
    a1.close()
    a2.close()


async def generate_image(chat_id: int, uid1: int, uid2: int, date: str) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tok = uuid.uuid4().hex[:8]
    p1 = await safe_photo(uid1, f"pfp1_{chat_id}_{uid1}_{tok}.png")
    p2 = await safe_photo(uid2, f"pfp2_{chat_id}_{uid2}_{tok}.png")

    out_path = OUT_DIR / f"couple_{chat_id}_{date.replace('/','-')}.png"
    try:
        await asyncio.to_thread(_compose_couple_image, p1, p2, out_path)
    finally:
        for pf in (p1, p2):
            try:
                if pf != FALLBACK and pf.exists() and pf.parent == OUT_DIR:
                    pf.unlink()
            except Exception:
                pass

    return str(out_path)


@app.on_message(filters.command("couple"))
async def couples_handler(_, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("**ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.**")

    wait = await message.reply("🦋")
    cid = message.chat.id
    date = today()

    async with _lock_for_chat(cid):
        record = await get_couple(cid, date)
        if record:
            uid1, uid2, img_path = record["user1"], record["user2"], record["img"]
            user1 = await safe_get_user(uid1)
            user2 = await safe_get_user(uid2)

            if not (user1 and user2) or not img_path or not Path(img_path).exists():
                record = None

        if not record:
            members = [
                m.user.id async for m in app.get_chat_members(cid, limit=250)
                if m.user and not m.user.is_bot
            ]
            if len(members) < 2:
                await wait.edit("**ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴜsᴇʀs ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ.**")
                return

            tries = 0
            while tries < 5:
                uid1, uid2 = random.sample(members, 2)
                user1 = await safe_get_user(uid1)
                user2 = await safe_get_user(uid2)
                if user1 and user2:
                    break
                tries += 1
            else:
                await wait.edit("**ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴠᴀʟɪᴅ ᴍᴇᴍʙᴇʀꜱ.**")
                return

            img_path = await generate_image(cid, uid1, uid2, date)
            await save_couple(cid, date, {"user1": uid1, "user2": uid2}, img_path)

    caption = (
        "💌 **ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ!** 💗\n\n"
        "╔═══✿═══❀═══✿═══╗\n"
        f"💌 **ᴛᴏᴅᴀʏ'ꜱ ᴄᴏᴜᴘʟᴇ:**\n⤷ {user1.mention} 💞 {user2.mention}\n"
        "╚═══✿═══❀═══✿═══╝\n\n"
        f"📅 **ɴᴇxᴛ ꜱᴇʟᴇᴄᴛɪᴏɴ:** `{tomorrow()}`\n\n"
        "💗 **ᴛᴀɢ ʏᴏʀ ᴄʀᴜꜱʜ — ʏᴏᴜ ᴍɪɢʜᴛ ʙᴇ ɴᴇxᴛ!** 😉" if False else (
        "💌 **ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ!** 💗\n\n"
        "╔═══✿═══❀═══✿═══╗\n"
        f"💌 **ᴛᴏᴅᴀʏ'ꜱ ᴄᴏᴜᴘʟᴇ:**\n⤷ {user1.mention} 💞 {user2.mention}\n"
        "╚═══✿═══❀═══✿═══╝\n\n"
        f"📅 **ɴᴇxᴛ ꜱᴇʟᴇᴄᴛɪᴏɴ:** `{tomorrow()}`\n\n"
        "💗 **ᴛᴀɢ ʏᴏᴜʀ ᴄʀᴜꜱʜ — ʏᴏᴜ ᴍɪɢʜᴛ ʙᴇ ɴᴇxᴛ!** 😉"
        )
    )

    try:
        await message.reply_photo(img_path, caption=caption)
    except Exception:
        await message.reply_text(caption)
    finally:
        try:
            await wait.delete()
        except Exception:
            pass
