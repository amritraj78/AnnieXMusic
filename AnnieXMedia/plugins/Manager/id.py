# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import LinkPreviewOptions, Message

from AnnieXMedia import app


@app.on_message(filters.command("id"))
async def get_id(client, message: Message):
    chat, user, reply = message.chat, message.from_user, message.reply_to_message
    out = []

    if message.link:
        out.append(f"**[ᴍᴇssᴀɢᴇ ɪᴅ:]({message.link})** `{message.id}`")
    else:
        out.append(f"**ᴍᴇssᴀɢᴇ ɪᴅ:** `{message.id}`")

    if user:
        out.append(f"**[ʏᴏᴜʀ ɪᴅ:](tg://user?id={user.id})** `{user.id}`")
    elif message.sender_chat:
        out.append(f"**sᴇɴᴅᴇʀ ᴄʜᴀᴛ ɪᴅ:** `{message.sender_chat.id}`")

    if len(message.command) == 2:
        try:
            target = message.text.split(maxsplit=1)[1]
            tgt_user = await client.get_users(target)
            out.append(f"**[ᴜsᴇʀ ɪᴅ:](tg://user?id={tgt_user.id})** `{tgt_user.id}`")
        except Exception:
            return await message.reply_text("**ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.**")

    if chat.username and str(chat.type).lower() != "chattype.private" and "private" not in str(chat.type).lower():
        out.append(f"**[ᴄʜᴀᴛ ɪᴅ:](https://t.me/{chat.username})** `{chat.id}`")
    else:
        out.append(f"**ᴄʜᴀᴛ ɪᴅ:** `{chat.id}`")

    if reply:
        if reply.link:
            out.append(f"**[ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:]({reply.link})** `{reply.id}`")
        else:
            out.append(f"**ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:** `{reply.id}`")

        if reply.from_user:
            out.append(
                f"**[ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:](tg://user?id={reply.from_user.id})** "
                f"`{reply.from_user.id}`"
            )

        if reply.forward_from_chat:
            out.append(
                f"ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀɴɴᴇʟ **{reply.forward_from_chat.title}** "
                f"ʜᴀs ɪᴅ `{reply.forward_from_chat.id}`"
            )

        if reply.sender_chat:
            out.append(f"ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ: `{reply.sender_chat.id}`")

    await message.reply_text(
        "\n".join(out),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
        parse_mode=ParseMode.MARKDOWN,
    )
