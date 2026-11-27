# Authored By Certified Coders © 2025
import asyncio
import csv
from io import BytesIO, StringIO
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from AnnieXMedia import app
from AnnieXMedia.utils.admin_check import is_admin
from AnnieXMedia.utils.admin_filters import admin_filter
from config import BANNED_USERS

_MAX_EXPORT_MEMBERS = 50000


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection in CSV exports."""
    s = str(value or "Unknown").replace("\r", " ").replace("\n", " ")
    if s.startswith(("=", "+", "-", "@", "\t")):
        return "'" + s
    return s


async def collect_members(chat_id, processing_msg):
    members_list = []
    async for member in app.get_chat_members(chat_id):
        if not member.user:
            continue
        members_list.append({
            "username": member.user.username or member.user.first_name or "Unknown",
            "userid": member.user.id,
        })
        if len(members_list) >= _MAX_EXPORT_MEMBERS:
            break
        if len(members_list) % 250 == 0:
            try:
                await processing_msg.edit_text(f"Collected {len(members_list)} members so far...")
            except FloodWait as e:
                await asyncio.sleep(min(e.value, 10))
            except Exception:
                pass
    return members_list


@app.on_message(filters.command("user") & admin_filter & ~BANNED_USERS)
async def user_command(_, message):
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("CSV", callback_data="members_csv"),
            InlineKeyboardButton("TXT", callback_data="members_txt"),
        ]]
    )
    await message.reply_text(
        "In which format do you want the members list?",
        reply_markup=keyboard,
    )


@app.on_callback_query(filters.regex("^members_") & ~BANNED_USERS)
async def members_format_callback(_, callback_query):
    if not callback_query.message or not callback_query.message.chat:
        return
    if not await is_admin(callback_query):
        return await callback_query.answer("Only admins can export members list.", show_alert=True)
    format_choice = callback_query.data.split("_", 1)[1].lower()
    await callback_query.answer()

    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    processing_msg = await callback_query.message.reply_text("Collecting members, please wait...")
    chat_id = callback_query.message.chat.id
    members_list = await collect_members(chat_id, processing_msg)

    if format_choice == "csv":
        csv_text = StringIO()
        writer = csv.DictWriter(csv_text, fieldnames=["username", "userid"])
        writer.writeheader()
        for member in members_list:
            writer.writerow({"username": _csv_safe(member["username"]), "userid": member["userid"]})
        file_bytes = BytesIO(csv_text.getvalue().encode("utf-8"))
        file_name = "members.csv"
        caption_text = "Here is the list of chat members in CSV format."
    else:
        text_lines = [f"{member['username']} - {member['userid']}" for member in members_list]
        file_bytes = BytesIO("\n".join(text_lines).encode("utf-8"))
        file_name = "members.txt"
        caption_text = "Here is the list of chat members in TXT format."

    file_bytes.seek(0)
    await app.send_document(
        chat_id,
        document=file_bytes,
        caption=caption_text,
        file_name=file_name,
    )
    try:
        await processing_msg.delete()
    except Exception:
        pass
    try:
        await callback_query.message.delete()
    except Exception:
        pass
