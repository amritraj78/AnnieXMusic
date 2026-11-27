# Authored By Certified Coders © 2025
import re
from typing import Union

from pyrogram import Client, filters, types
from pyrogram.types import InlineKeyboardMarkup, LinkPreviewOptions, Message

from AnnieXMedia import app
from AnnieXMedia.utils.database import get_lang
from AnnieXMedia.utils.decorators.language import LanguageStart, languageCB
from AnnieXMedia.utils.inline.help import (
    action_sub_menu,
    first_page,
    help_back_markup,
    private_help_panel,
    second_page,
)
from AnnieXMedia.utils.inline.start import private_panel
from config import BANNED_USERS, HELP_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers

# ────────────────────────────────────────────────  /help entrypoints ──

async def _safe_help_edit(cb: types.CallbackQuery, text: str, reply_markup=None):
    try:
        await cb.answer()
    except Exception:
        pass
    msg = cb.message
    if msg and (msg.photo or msg.video):
        try:
            return await cb.edit_message_caption(caption=text[:1024], reply_markup=reply_markup)
        except Exception:
            pass
    try:
        return await cb.edit_message_text(
            text=text[:4096],
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        try:
            return await cb.edit_message_caption(caption=text[:1024], reply_markup=reply_markup)
        except Exception:
            pass


@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex(r"^open_help$") & ~BANNED_USERS)
@LanguageStart
async def helper_private(client: Client, update: Union[Message, types.CallbackQuery], _):
    is_cb = isinstance(update, types.CallbackQuery)
    user_id = update.from_user.id if update.from_user else 0
    language = await get_lang(user_id)
    _ = get_string(language)

    keyboard = first_page(_)
    caption = _["help_1"].format(SUPPORT_CHAT)

    if is_cb:
        try:
            await update.answer()
        except Exception:
            pass
        await _safe_help_edit(update, caption, reply_markup=keyboard)
    else:
        try:
            await update.delete()
        except Exception:
            pass
        try:
            await update.reply_photo(
                photo=HELP_IMG_URL,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception:
            await update.reply_text(
                text=caption,
                reply_markup=keyboard
            )

# ────────────────────────────────────────────────  group /help notice ─

@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client: Client, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(
        _["help_2"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

# ────────────────────────────────────────────────  main help buttons ──

@app.on_callback_query(filters.regex(r"^help_callback hb(\d+)_p(\d+)$") & ~BANNED_USERS)
@languageCB
async def helper_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    match = re.match(r"^help_callback hb(\d+)_p(\d+)$", CallbackQuery.data)
    if not match:
        return await CallbackQuery.answer("Invalid callback.", show_alert=True)

    number = int(match.group(1))
    current_page = int(match.group(2))

    #── Action (1) gets its own sub-menu
    if number == 1:
        await _safe_help_edit(
            CallbackQuery,
            _["S_B_M"],
            reply_markup=action_sub_menu(_, current_page),
        )
        return

    #── All other categories
    help_text = getattr(helpers, f"HELP_{number}", None)
    if not help_text:
        return await CallbackQuery.answer("Invalid help topic.", show_alert=True)

    await _safe_help_edit(
        CallbackQuery,
        help_text,
        reply_markup=help_back_markup(_, current_page),
    )

# ─────────────────────────────────────────  pagination callbacks ─────

@app.on_callback_query(filters.regex(r"^help_next_(\d+)$") & ~BANNED_USERS)
@languageCB
async def help_next_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    if CallbackQuery.data == "help_next_2":
        await _safe_help_edit(
            CallbackQuery,
            _["help_1"].format(SUPPORT_CHAT),
            reply_markup=second_page(_),
        )
    else:
        await CallbackQuery.answer("No more pages.", show_alert=True)

@app.on_callback_query(filters.regex(r"^help_prev_(\d+)$") & ~BANNED_USERS)
@languageCB
async def help_prev_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    if CallbackQuery.data == "help_prev_1":
        await _safe_help_edit(
            CallbackQuery,
            _["help_1"].format(SUPPORT_CHAT),
            reply_markup=first_page(_),
        )
    else:
        await CallbackQuery.answer("No previous page.", show_alert=True)

@app.on_callback_query(filters.regex(r"^help_back_(\d+)$") & ~BANNED_USERS)
@languageCB
async def help_back_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    page = CallbackQuery.data.split("_")[-1]
    if page == "1":
        keyboard = first_page(_)
    elif page == "2":
        keyboard = second_page(_)
    else:
        return await CallbackQuery.answer("Invalid page.", show_alert=True)

    await _safe_help_edit(
        CallbackQuery,
        _["help_1"].format(SUPPORT_CHAT),
        reply_markup=keyboard,
    )

# ────────────────────────────────────────  sub-topic buttons (Action) ─

@app.on_callback_query(filters.regex(r"^action_prom_1$") & ~BANNED_USERS)
@languageCB
async def action_prom_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    await _safe_help_edit(
        CallbackQuery,
        helpers.HELP_1_PROMO,
        reply_markup=help_back_markup(_, 1),
    )

@app.on_callback_query(filters.regex(r"^action_pun_1$") & ~BANNED_USERS)
@languageCB
async def action_pun_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    await _safe_help_edit(
        CallbackQuery,
        helpers.HELP_1_PUNISH,
        reply_markup=help_back_markup(_, 1),
    )

# ────────────────────────────────────────────────  back to start panel ─

@app.on_callback_query(filters.regex(r"^back_to_main$") & ~BANNED_USERS)
@languageCB
async def back_to_main_cb(client: Client, CallbackQuery: types.CallbackQuery, _):
    out = private_panel(_)
    user_mention = CallbackQuery.from_user.mention if CallbackQuery.from_user else "User"
    await _safe_help_edit(
        CallbackQuery,
        _["start_2"].format(user_mention, app.mention),
        reply_markup=InlineKeyboardMarkup(out)
    )
