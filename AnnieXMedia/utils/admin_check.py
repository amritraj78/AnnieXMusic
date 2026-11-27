# Authored By Certified Coders © 2025
from pyrogram.types import CallbackQuery
from pyrogram.enums import ChatType, ChatMemberStatus


async def is_admin(message_or_cq) -> bool:
    if isinstance(message_or_cq, CallbackQuery):
        user = message_or_cq.from_user
        chat = message_or_cq.message.chat if message_or_cq.message else None
        client = message_or_cq._client
    else:
        user = message_or_cq.from_user
        chat = message_or_cq.chat
        client = message_or_cq._client
        if message_or_cq.sender_chat and chat and message_or_cq.sender_chat.id == chat.id:
            return True

    if not user or not chat:
        return False

    if chat.type not in (ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.GROUP):
        return False

    # Anonymous group admin must originate from chat's own sender_chat (never 777000 channel-link auto-forward)
    if user.id == 1087968824:
        sender_chat = None if isinstance(message_or_cq, CallbackQuery) else message_or_cq.sender_chat
        return bool(sender_chat and sender_chat.id == chat.id)

    try:
        member = await client.get_chat_member(chat.id, user.id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


async def is_group_owner(message_or_cq) -> bool:
    if isinstance(message_or_cq, CallbackQuery):
        user = message_or_cq.from_user
        chat = message_or_cq.message.chat if message_or_cq.message else None
        client = message_or_cq._client
    else:
        user = message_or_cq.from_user
        chat = message_or_cq.chat
        client = message_or_cq._client

    if not user or not chat:
        return False

    if chat.type not in (ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.GROUP):
        return False

    # Do not treat service/anonymous accounts (777000, 1087968824) as group creator
    if user.id in (777000, 1087968824):
        return False

    try:
        member = await client.get_chat_member(chat.id, user.id)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False
