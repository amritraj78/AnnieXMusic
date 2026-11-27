# Authored By Certified Coders © 2025
from pyrogram import filters
from AnnieXMedia import app
from config import LOGGER_ID, OWNER_ID

destination_group_id = LOGGER_ID

@app.on_message(filters.command(["post"], prefixes=["/", "."]) & filters.user(OWNER_ID))
async def copy_messages(_, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message to post it. Usage: /post [chat_id]")

    dest = destination_group_id
    if len(message.command) > 1:
        try:
            dest = int(message.command[1])
        except ValueError:
            dest = message.command[1]

    try:
        await message.reply_to_message.copy(dest)
        await message.reply("ᴘᴏsᴛ sᴜᴄᴄᴇssғᴜʟ ᴅᴏɴᴇ ")
    except Exception as e:
        await message.reply(f"Failed to post: {e}")
