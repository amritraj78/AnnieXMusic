# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
from gpytranslate import Translator

translator = Translator()


@app.on_message(filters.command("tr"))
async def translate(_, message: Message):
    reply = message.reply_to_message

    if not reply or not (reply.text or reply.caption):
        return await message.reply_text("📌 ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴛᴇxᴛ ᴏʀ ᴄᴀᴘᴛɪᴏɴ ᴛᴏ ᴛʀᴀɴsʟᴀᴛᴇ.")

    content = (reply.text or reply.caption)[:4000]

    try:
        if len(message.command) > 1 and message.text:
            arg = message.text.split(maxsplit=1)[1].strip().lower()
            if "//" in arg:
                source_lang, target_lang = arg.split("//", 1)
            else:
                source_lang = await translator.detect(content)
                target_lang = arg
        else:
            source_lang = await translator.detect(content)
            target_lang = "en"

        result = await translator(content, sourcelang=source_lang, targetlang=target_lang)
        translated = (getattr(result, "text", None) or "").strip()
        if not translated:
            return await message.reply_text("❌ **ᴛʀᴀɴsʟᴀᴛɪᴏɴ ʀᴇᴛᴜʀɴᴇᴅ ᴇᴍᴘᴛʏ ᴛᴇxᴛ.**")

        safe_src = str(source_lang).replace("`", "'")[:32]
        safe_dst = str(target_lang).replace("`", "'")[:32]
        safe_txt = translated.replace("`", "'")[:3500]
        await message.reply_text(
            f"🌐 **ᴛʀᴀɴsʟᴀᴛᴇᴅ:** `{safe_src}` ➜ `{safe_dst}`\n\n"
            f"`{safe_txt}`"
        )
    except Exception as e:
        safe_err = str(e).replace("`", "'")[:500]
        await message.reply_text(f"❌ **ᴛʀᴀɴsʟᴀᴛɪᴏɴ ꜰᴀɪʟᴇᴅ:** `{safe_err}`")
