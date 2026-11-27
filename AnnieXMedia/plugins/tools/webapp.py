# Authored By Certified Coders © 2025
"""Telegram Mini App, Neon Arcade Games, and BotFather Game callback handlers."""
import contextlib
import html

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

import config
from AnnieXMedia import app
from AnnieXMedia.core.webapp_auth import set_webapp_menu_button, sign_game_launch
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.misc import SUDOERS
from config import BANNED_USERS

log = LOGGER(__name__)

_WEBAPP_URL = config.WEBAPP_URL
_GAME_NAME = config.GAME_SHORT_NAME

_GAME_KEY_ALIASES = {
    "snake": "snake",
    "flappy": "flappy",
    "beats": "beats",
    "tiles": "beats",
}


def build_private_webapp_markup() -> InlineKeyboardMarkup:
    """Return private-chat WebApp buttons (Telegram only allows web_app buttons in private chats)."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎵 Open Music Mini App", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/app"))],
            [
                InlineKeyboardButton("🔍 Search & Play", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/app?tab=search")),
                InlineKeyboardButton("🕹️ Neon Arcade", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/game")),
            ],
        ]
    )


def build_private_arcade_markup() -> InlineKeyboardMarkup:
    """Return private-chat WebApp buttons for all 3 Neon Arcade games."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎹 Play Beat Tiles", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/game?game=beats"))],
            [
                InlineKeyboardButton("🐍 Neon Snake", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/game?game=snake")),
                InlineKeyboardButton("⚡ Flappy Beat", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/game?game=flappy")),
            ],
            [InlineKeyboardButton("🎵 Back to Music Mini App", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/app"))],
        ]
    )


@app.on_message(filters.command(["app", "webapp", "miniapp"]) & ~BANNED_USERS)
async def cmd_app(_, message: Message):
    """Open the AnnieXMusic Mini App cleanly in both private and group chats."""
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text(
            "🎵 **AnnieXMusic Mini App**\n\n"
            "• Live Voice Chat Player & Queue Controls\n"
            "• Instant Song Search & Queue into Group VC\n"
            "• Built-in 3-in-1 Neon Arcade & Leaderboards",
            reply_markup=build_private_webapp_markup(),
        )

    bot_user = getattr(app, "username", None) or config.BOT_USERNAME
    return await message.reply_text(
        "🎵 **AnnieXMusic Mini App**\n\n"
        "Tap below to launch the Web App directly with this chat connected!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎵 Open Music Mini App", url=f"https://t.me/{bot_user}?start=webapp")]]
        ),
    )


@app.on_message(filters.command(["game", "arcade"]) & ~BANNED_USERS)
async def cmd_game(_, message: Message):
    """Launch BotFather native game (if configured) or Neon Arcade Web App."""
    cmd = message.command[0].lower() if message.command else "game"
    arg = message.command[1].lower() if len(message.command or []) > 1 else ""
    target_game = _GAME_KEY_ALIASES.get(arg, "")

    # Try BotFather /newgame card when `/game` is called without a specific sub-game
    if cmd == "game" and not target_game and _GAME_NAME:
        with contextlib.suppress(Exception):
            await app.send_game(message.chat.id, _GAME_NAME)
            return

    if message.chat.type == ChatType.PRIVATE:
        if target_game:
            return await message.reply_text(
                f"🕹️ **Launching {target_game.title()}**",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("▶ Play Now", web_app=WebAppInfo(url=f"{_WEBAPP_URL}/game?game={target_game}"))]]
                ),
            )
        return await message.reply_text(
            "🕹️ **Neon Arcade**\n\nBeat Tiles · Neon Snake · Flappy Beat\nCompete for #1 on the live leaderboard!",
            reply_markup=build_private_arcade_markup(),
        )

    bot_user = getattr(app, "username", None) or config.BOT_USERNAME
    return await message.reply_text(
        "🕹️ **Neon Arcade**\n\nBeat Tiles · Neon Snake · Flappy Beat\nTap below to play!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎮 Open Neon Arcade", url=f"https://t.me/{bot_user}?start=game")]]
        ),
    )


def _is_game_callback(_, __, query: CallbackQuery) -> bool:
    return bool(getattr(query, "game_short_name", None))


@app.on_callback_query(filters.create(_is_game_callback) & ~BANNED_USERS)
async def game_callback(_, query: CallbackQuery):
    """Answer BotFather callback_game query with a signed score-sync URL."""
    if not query.from_user or not _WEBAPP_URL.startswith("https://"):
        return await query.answer("⚠️ Game temporarily unavailable.", show_alert=True)
    short = str(query.game_short_name or "").strip().lower()
    game_mode = _GAME_KEY_ALIASES.get(short, "beats")
    user = query.from_user
    payload = {
        "user_id": user.id,
        "name": (f"{user.first_name or ''} {user.last_name or ''}".strip() or "Player")[:48],
        "username": user.username or "",
    }
    if getattr(query, "inline_message_id", None):
        payload["inline_message_id"] = query.inline_message_id
    elif query.message:
        payload["chat_id"] = query.message.chat.id
        payload["message_id"] = query.message.id

    token = sign_game_launch(payload)
    game_url = f"{_WEBAPP_URL}/game?game={game_mode}&launch={token}" if token else f"{_WEBAPP_URL}/game?game={game_mode}"
    await query.answer(url=game_url)


@app.on_message(filters.command("setmenubutton") & SUDOERS)
async def cmd_setmenubutton(_, message: Message):
    """Set the bot's menu button to open the Mini App."""
    if not _WEBAPP_URL.startswith("https://"):
        return await message.reply_text("⚠️ WEBAPP_URL must start with `https://`.")
    try:
        await set_webapp_menu_button(app, f"{_WEBAPP_URL}/app")
        await message.reply_text("✅ Menu button updated! Tap **🎵 Open App** in private chat.")
    except Exception as e:
        await message.reply_text(f"❌ Failed to set menu button:\n<code>{html.escape(str(e))}</code>")
