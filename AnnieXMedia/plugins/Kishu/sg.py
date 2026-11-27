# Authored By Certified Coders © 2025
import asyncio
import random

from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.raw.functions.messages import DeleteHistory

from AnnieXMedia import userbot as us, app
from AnnieXMedia.core.userbot import assistants


_sg_lock = asyncio.Lock()


@app.on_message(filters.command("sg"))
async def sg(client: Client, message: Message):
    if not assistants or 1 not in assistants or not getattr(us, "one", None):
        return await message.reply("❌ No active userbot assistant found!")

    ubot = us.one
    status_msg = await message.reply("👀")

    try:
        if message.reply_to_message:
            if not message.reply_to_message.from_user:
                return await status_msg.edit("❌ Cannot get history for channel or anonymous message.")
            target_user_id = message.reply_to_message.from_user.id
        else:
            parts = message.text.split()
            if len(parts) < 2:
                return await status_msg.edit("❌ Usage: `/sg` username / id / reply", parse_mode=enums.ParseMode.MARKDOWN)

            target_input = parts[1].strip()
            if target_input.lstrip("-").isdigit():
                target_user_id = int(target_input)
            else:
                user = await client.get_users(target_input)
                if isinstance(user, list):
                    user = user[0] if user else None
                if not user:
                    raise ValueError("User not found")
                target_user_id = user.id
    except Exception:
        return await status_msg.edit("❌ Invalid user. Please reply to a user or provide a valid username/id.")

    sangmata_bots = ["sangmata_bot", "sangmata_beta_bot"]
    sg_bot = random.choice(sangmata_bots)

    async with _sg_lock:
        try:
            sent_msg = await ubot.send_message(sg_bot, str(target_user_id))
        except Exception as e:
            safe_err = str(e).replace("`", "'")
            return await status_msg.edit(f"❌ Failed to contact @`{sg_bot}`\n`{safe_err}`", parse_mode=enums.ParseMode.MARKDOWN)

        try:
            await asyncio.sleep(2.0)

            found = False
            async for stalk in ubot.get_chat_history(sg_bot, limit=6):
                if stalk.id > sent_msg.id and stalk.text:
                    await message.reply(stalk.text)
                    found = True
                    break

            if not found:
                await message.reply("🤖 Bot didn't return any username history.")
        finally:
            try:
                peer = await ubot.resolve_peer(sg_bot)
                await ubot.invoke(DeleteHistory(peer=peer, max_id=0, revoke=False))
            except Exception:
                pass
            try:
                await status_msg.delete()
            except Exception:
                pass
