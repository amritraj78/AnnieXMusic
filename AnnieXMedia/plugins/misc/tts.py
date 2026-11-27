# Authored By Certified Coders © 2025
import asyncio
import os
import tempfile
import time
from collections import OrderedDict
from math import ceil
from typing import Dict, List, Tuple

import edge_tts
from pyrogram import Client, filters
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from AnnieXMedia import app

_voice_sessions: OrderedDict[Tuple[int, int], Tuple[str, float]] = OrderedDict()
_MAX_VOICE_SESSIONS = 2000
_SESSION_TTL = 900.0
_MAX_TTS_CHARS = 1500
_voices: List[dict] = []
_languages: List[str] = []
_VOICES_LOCK = asyncio.Lock()

PER_ROW = 4
PER_PAGE = 16


async def _init_voices() -> None:
    global _voices, _languages
    if _voices:
        return

    async with _VOICES_LOCK:
        if _voices:
            return

        raw = await edge_tts.list_voices()
        _voices = [
            {
                "short_name": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
            }
            for v in raw
        ]
        _languages = sorted({v["locale"].split("-", 1)[0] for v in _voices})


def _paginate(items: List[str], page: int) -> Tuple[List[str], int, int]:
    total = len(items)
    pages = max(1, ceil(total / PER_PAGE))
    page = max(1, min(page, pages))
    start = (page - 1) * PER_PAGE
    return items[start : start + PER_PAGE], pages, start


def _build_keyboard(
    items: List[str],
    step: str,
    extra: Dict[str, str],
    page: int,
) -> InlineKeyboardMarkup:
    if not items:
        return InlineKeyboardMarkup([])

    page_items, total_pages, start_idx = _paginate(items, page)
    row_width = 2 if step == "model" else PER_ROW

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(page_items), row_width):
        chunk = page_items[i : i + row_width]
        rows.append(
            [
                InlineKeyboardButton(
                    text=item,
                    callback_data="tts:"
                    + f"s={step}"
                    + "".join(f"|{k}={v}" for k, v in extra.items())
                    + f"|p={page}|i={start_idx + i + offset}",
                )
                for offset, item in enumerate(chunk)
            ]
        )

    nav: List[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "◀️ Prev",
                callback_data="tts:"
                + f"s={step}"
                + "".join(f"|{k}={v}" for k, v in extra.items())
                + f"|p={page-1}",
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                "Next ▶️",
                callback_data="tts:"
                + f"s={step}"
                + "".join(f"|{k}={v}" for k, v in extra.items())
                + f"|p={page+1}",
            )
        )
    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


def _session_key(chat_id: int, user_id: int) -> Tuple[int, int]:
    return chat_id, user_id


def _put_voice_session(key: Tuple[int, int], text: str) -> None:
    now = time.monotonic()
    while _voice_sessions:
        oldest_key, (_, ts) = next(iter(_voice_sessions.items()))
        if now - ts > _SESSION_TTL or len(_voice_sessions) >= _MAX_VOICE_SESSIONS:
            _voice_sessions.popitem(last=False)
        else:
            break
    _voice_sessions[key] = (text, now)
    _voice_sessions.move_to_end(key)


def _get_voice_session(key: Tuple[int, int]) -> str | None:
    entry = _voice_sessions.get(key)
    if not entry:
        return None
    text, ts = entry
    if time.monotonic() - ts > _SESSION_TTL:
        _voice_sessions.pop(key, None)
        return None
    return text


def _cleanup(path: str) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


async def _synthesize(voice: str, text: str, out_path: str) -> None:
    comm = edge_tts.Communicate(text=text, voice=voice)
    await asyncio.wait_for(comm.save(out_path), timeout=30.0)


@app.on_message(filters.command("voices"))
async def cmd_voices(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide the text to convert.\n\nExample: `/voices Hello world`",
            parse_mode=ParseMode.MARKDOWN,
        )

    if not message.from_user:
        return await message.reply_text("❌ Please run this command as a standard user.")

    text = " ".join(message.command[1:]).strip()
    if len(text) > _MAX_TTS_CHARS:
        return await message.reply_text(f"❌ Text too long (max {_MAX_TTS_CHARS} characters).")

    await _init_voices()

    _put_voice_session(_session_key(message.chat.id, message.from_user.id), text)

    kb = _build_keyboard(_languages, step="lang", extra={}, page=1)
    await message.reply_text(
        "🌐 **Step 1:** Select a language",
        reply_markup=kb,
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.command("tts"))
async def cmd_tts(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "❌ Usage:\n`/tts <voice_model> <text>`\nAlternatively try `/voices` for guided selection.",
            parse_mode=ParseMode.MARKDOWN,
        )

    await _init_voices()

    voice = message.command[1].strip()
    text = " ".join(message.command[2:]).strip()
    if len(text) > _MAX_TTS_CHARS:
        return await message.reply_text(f"❌ Text too long (max {_MAX_TTS_CHARS} characters).")

    if not any(v["short_name"] == voice for v in _voices):
        safe_voice = voice.replace("`", "'")
        return await message.reply_text(
            f"⚠️ Unknown voice: `{safe_voice}`\nUse `/voiceall` or `/voices` to browse voices.",
            parse_mode=ParseMode.MARKDOWN,
        )

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp = tmp_file.name

    try:
        await client.send_chat_action(message.chat.id, ChatAction.RECORD_AUDIO)
        await _synthesize(voice, text, tmp)

        await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_AUDIO)
        await client.send_audio(
            chat_id=message.chat.id,
            audio=tmp,
            caption=f"🗣️ `{voice}`",
            reply_to_message_id=message.id,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        await message.reply_text(f"⚠️ Failed to generate speech: {exc}")
    finally:
        await asyncio.to_thread(_cleanup, tmp)


def _regions_for_lang(lang: str) -> List[str]:
    return sorted(
        {
            v["locale"].split("-", 1)[1]
            for v in _voices
            if v["locale"].startswith(f"{lang}-") and "-" in v["locale"]
        }
    )


def _models_for_locale(lang: str, region: str) -> List[str]:
    locale = f"{lang}-{region}"
    return sorted([v["short_name"] for v in _voices if v["locale"] == locale])


@app.on_callback_query(filters.regex(r"^tts:"))
async def cb_tts(client: Client, callback: CallbackQuery):
    if not callback.from_user:
        return await callback.answer("❌ User not found.", show_alert=True)
    if not callback.message:
        return await callback.answer()

    data = callback.data[4:]
    parts = dict(p.split("=", 1) for p in data.split("|") if "=" in p)
    step = parts.get("s")
    try:
        page = max(1, int(parts.get("p", "1")))
    except ValueError:
        return await callback.answer("⚠️ Invalid callback data.", show_alert=True)

    await _init_voices()

    key = _session_key(callback.message.chat.id, callback.from_user.id)
    text = _get_voice_session(key)
    if not text:
        return await callback.answer(
            "⚠️ Session expired. Send /voices again.", show_alert=True
        )

    if step == "lang":
        if "i" not in parts:
            kb = _build_keyboard(_languages, "lang", {}, page)
            await callback.answer()
            return await callback.edit_message_text(
                "🌐 **Step 1:** Select a language",
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
            )

        try:
            idx = int(parts["i"])
            lang = _languages[idx]
        except (ValueError, IndexError):
            return await callback.answer("⚠️ Selection expired.", show_alert=True)

        regions = _regions_for_lang(lang)
        kb = _build_keyboard(regions, "region", {"l": lang}, 1)
        await callback.answer()
        return await callback.edit_message_text(
            "🌍 **Step 2:** Select a region",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN,
        )

    if step == "region":
        lang = parts.get("l")
        if not lang:
            return await callback.answer("⚠️ Session data incomplete.", show_alert=True)
        regions = _regions_for_lang(lang)

        if "i" not in parts:
            kb = _build_keyboard(regions, "region", {"l": lang}, page)
            await callback.answer()
            return await callback.edit_message_text(
                "🌍 **Step 2:** Select a region",
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
            )

        try:
            idx = int(parts["i"])
            region = regions[idx]
        except (ValueError, IndexError):
            return await callback.answer("⚠️ Selection expired.", show_alert=True)

        models = _models_for_locale(lang, region)
        kb = _build_keyboard(models, "model", {"l": lang, "r": region}, 1)
        await callback.answer()
        return await callback.edit_message_text(
            "🔊 **Step 3:** Choose a voice model",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN,
        )

    if step == "model":
        lang = parts.get("l")
        region = parts.get("r")
        if not lang or not region:
            return await callback.answer("⚠️ Session data incomplete.", show_alert=True)
        models = _models_for_locale(lang, region)

        if "i" not in parts:
            kb = _build_keyboard(models, "model", {"l": lang, "r": region}, page)
            await callback.answer()
            return await callback.edit_message_text(
                "🔊 **Step 3:** Choose a voice model",
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
            )

        try:
            idx = int(parts["i"])
            voice = models[idx]
        except (ValueError, IndexError):
            return await callback.answer("⚠️ Selection expired.", show_alert=True)

        await callback.answer("🔊 Synthesizing audio...")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp = tmp_file.name

        try:
            await client.send_chat_action(callback.message.chat.id, ChatAction.RECORD_AUDIO)
            await _synthesize(voice, text, tmp)

            await client.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_AUDIO)
            await client.send_audio(
                chat_id=callback.message.chat.id,
                audio=tmp,
                caption=f"🗣️ `{voice}`",
                reply_to_message_id=callback.message.reply_to_message.id if callback.message.reply_to_message else callback.message.id,
                parse_mode=ParseMode.MARKDOWN,
            )
            await callback.edit_message_text("✅ Audio generated successfully!")
        except Exception as exc:
            await callback.message.reply_text(f"⚠️ Generation failed: {exc}")
        finally:
            await asyncio.to_thread(_cleanup, tmp)
            _voice_sessions.pop(key, None)
        return

    await callback.answer("🤔 Unknown action. Send /voices again.", show_alert=True)


@app.on_message(filters.command("voiceall"))
async def cmd_voiceall(client: Client, message: Message):
    await _init_voices()

    sorted_voices = sorted(_voices, key=lambda v: v["short_name"])
    lines = [
        f"{v['short_name']} — {v['locale']} ({v['gender']})" for v in sorted_voices
    ]

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        path = tmp_file.name
        tmp_file.write("\n".join(lines).encode("utf-8"))

    try:
        await message.reply_document(document=path, caption="📋 List of all available voices")
    finally:
        await asyncio.to_thread(_cleanup, path)
