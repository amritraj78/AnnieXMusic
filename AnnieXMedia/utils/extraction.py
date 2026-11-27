# Authored By Certified Coders © 2025
from typing import Optional
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, User

from AnnieXMedia import app


async def extract_user(m: Message) -> Optional[User]:
    if m.reply_to_message:
        if m.reply_to_message.from_user:
            return m.reply_to_message.from_user
        return None

    if len(m.command) > 1:
        user_input = m.command[1].strip()
        if m.entities:
            for ent in m.entities:
                if ent.type == MessageEntityType.TEXT_MENTION and ent.user:
                    return ent.user
        try:
            target = int(user_input) if user_input.isdecimal() else user_input
            return await app.get_users(target)
        except Exception:
            return None

    return None
