# Authored By Certified Coders © 2025
from pyrogram.types import LinkPreviewOptions
from AnnieXMedia import app
from config import SUPPORT_CHAT
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import get_lang, is_maintenance
from strings import get_string


def language(mystic):
    async def wrapper(_, message, **kwargs):
        if await is_maintenance() is False:
            if not message.from_user or message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
        try:
            await message.delete()
        except:
            pass

        try:
            language = await get_lang(message.chat.id)
            language = get_string(language)
        except:
            language = get_string("en")
        return await mystic(_, message, language)

    return wrapper


def languageCB(mystic):
    async def wrapper(_, CallbackQuery, **kwargs):
        if await is_maintenance() is False:
            if not CallbackQuery.from_user or CallbackQuery.from_user.id not in SUDOERS:
                return await CallbackQuery.answer(
                    f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    show_alert=True,
                )
        try:
            chat_id = CallbackQuery.message.chat.id if CallbackQuery.message else 0
            language = await get_lang(chat_id)
            language = get_string(language)
        except Exception:
            language = get_string("en")
        return await mystic(_, CallbackQuery, language)

    return wrapper


def LanguageStart(mystic):
    async def wrapper(_, message, **kwargs):
        try:
            chat = getattr(message, "chat", None)
            if not chat and getattr(message, "message", None):
                chat = getattr(message.message, "chat", None)
            chat_id = chat.id if chat else (message.from_user.id if getattr(message, "from_user", None) else 0)
            language = await get_lang(chat_id)
            language = get_string(language)
        except Exception:
            language = get_string("en")
        return await mystic(_, message, language)

    return wrapper
