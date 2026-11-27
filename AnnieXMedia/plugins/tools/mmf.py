# Authored By Certified Coders © 2025
import os
import asyncio
import uuid
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app

def _sync_drawText(image_path: str, text: str, output_file: str) -> str:
    try:
        with Image.open(image_path) as orig:
            img = orig.convert("RGBA")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    i_width, i_height = img.size

    if os.name == "nt":
        fnt = "arial.ttf"
    else:
        fnt = "./AnnieXMedia/assets/default.ttf"

    try:
        m_font = ImageFont.truetype(fnt, max(12, int((70 / 640) * i_width)))
    except Exception:
        m_font = ImageFont.load_default()

    if ";" in text:
        upper_text, lower_text = text.split(";", 1)
    else:
        upper_text = text
        lower_text = ""

    draw = ImageDraw.Draw(img)
    current_h, pad = 10, 5

    if upper_text:
        for u_text in textwrap.wrap(upper_text, width=15):
            uwl, uht, uwr, uhb = m_font.getbbox(u_text)
            u_width, u_height = uwr - uwl, uhb - uht

            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                draw.text(
                    xy=(((i_width - u_width) / 2) + dx, int((current_h / 640) * i_width) + dy),
                    text=u_text,
                    font=m_font,
                    fill=(0, 0, 0),
                )
            draw.text(
                xy=((i_width - u_width) / 2, int((current_h / 640) * i_width)),
                text=u_text,
                font=m_font,
                fill=(255, 255, 255),
            )
            current_h += u_height + pad

    if lower_text:
        for l_text in textwrap.wrap(lower_text, width=15):
            uwl, uht, uwr, uhb = m_font.getbbox(l_text)
            u_width, u_height = uwr - uwl, uhb - uht

            base_y = i_height - u_height - int((20 / 640) * i_width)
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                draw.text(
                    xy=(((i_width - u_width) / 2) + dx, base_y + dy),
                    text=l_text,
                    font=m_font,
                    fill=(0, 0, 0),
                )
            draw.text(
                xy=((i_width - u_width) / 2, base_y),
                text=l_text,
                font=m_font,
                fill=(255, 255, 255),
            )
            current_h += u_height + pad

    img.save(output_file, "webp")
    return output_file


@app.on_message(filters.command("mmf"))
async def mmf(_, message: Message):
    chat_id = message.chat.id
    reply_message = message.reply_to_message

    if len(message.text.split()) < 2:
        await message.reply_text("**Give me text after /mmf to memify.**")
        return

    if not reply_message:
        await message.reply_text("❌ **Please reply to an image or sticker to memify.**")
        return

    msg = await message.reply_text("❄️")
    text = message.text.split(None, 1)[1]
    file = None
    output_file = None
    try:
        file = await app.download_media(reply_message)
        if not file:
            return await msg.edit("❌ **Could not download media.**")

        output_file = f"memify_{chat_id}_{message.id}_{uuid.uuid4().hex[:6]}.webp"
        await asyncio.to_thread(_sync_drawText, file, text, output_file)
        await app.send_document(chat_id, document=output_file)
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ Failed to memify.\nError: {e}")
    finally:
        if file and os.path.exists(file):
            try:
                os.remove(file)
            except Exception:
                pass
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception:
                pass
