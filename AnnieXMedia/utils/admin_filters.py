# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery
from AnnieXMedia.utils.admin_check import is_admin, is_group_owner
from AnnieXMedia.misc import SUDOERS
from config import OWNER_ID


def sudo_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    user = obj.from_user if isinstance(obj, CallbackQuery) else getattr(obj, "from_user", None)
    sender_chat = getattr(obj, "sender_chat", None) if not isinstance(obj, CallbackQuery) else None
    return bool(
        (
            (user and user.id in SUDOERS)
            or (sender_chat and sender_chat.id in SUDOERS)
        )
        and not getattr(obj, "edit_date", False)
    )

sudo_filter = filters.create(func=sudo_filter_func, name="SudoUsersFilter")


async def admin_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    if getattr(obj, "edit_date", False):
        return False
    return await is_admin(obj)

admin_filter = filters.create(func=admin_filter_func, name="AdminFilter")


async def group_owner_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    if getattr(obj, "edit_date", False):
        return False
    return await is_group_owner(obj)

owner_filter = filters.create(func=group_owner_filter_func, name="GroupOwnerFilter")


def bot_owner_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    user = obj.from_user if isinstance(obj, CallbackQuery) else getattr(obj, "from_user", None)
    return bool(
        user
        and user.id == OWNER_ID
        and not getattr(obj, "edit_date", False)
    )

dev_filter = filters.create(func=bot_owner_filter_func, name="BotOwnerFilter")
