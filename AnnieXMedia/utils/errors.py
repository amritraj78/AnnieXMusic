# Authored By Certified Coders © 2025
import html
import sys
import traceback
import os
from functools import wraps
from datetime import datetime

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from AnnieXMedia import app
from config import LOGGER_ID, DEBUG_IGNORE_LOG
from AnnieXMedia.utils.exceptions import is_ignored_error
from AnnieXMedia.utils.pastebin import ANNIEBIN
from AnnieXMedia.utils.security import redact_secrets


DEBUG_LOG_FILE = "ignored_errors.log"
MAX_DEBUG_LOG_BYTES = 5 * 1024 * 1024  # 5 MB cap for Koyeb ephemeral disk


# ========== Paste Fallback ==========

async def send_large_error(text: str, caption: str, filename: str):
    clean_text = redact_secrets(text)
    try:
        paste_url = await ANNIEBIN(clean_text)
        if paste_url:
            await app.send_message(LOGGER_ID, f"{caption}\n\n🔗 Paste: {paste_url}")
            return
    except Exception:
        pass

    path = f"{filename}.txt"
    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(clean_text)
        await app.send_document(LOGGER_ID, path, caption="❌ Error Log (Fallback)")
    except Exception:
        pass
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


# ========== Formatting & Routing ==========

def format_traceback(err, tb, label: str, extras: dict = None) -> str:
    exc_type = html.escape(type(err).__name__)
    parts = [
        f"🚨 <b>{html.escape(str(label))} Captured</b>",
        f"📍 <b>Error Type:</b> <code>{exc_type}</code>"
    ]
    if extras:
        parts.extend(
            [f"📌 <b>{html.escape(str(k))}:</b> <code>{html.escape(redact_secrets(str(v)))}</code>" for k, v in extras.items()]
        )
    parts.append(f"\n<b>Traceback:</b>\n<pre>{html.escape(redact_secrets(str(tb)))}</pre>")
    return "\n".join(parts)

async def handle_trace(err, tb, label, filename, extras=None):
    clean_tb = redact_secrets(str(tb))
    if is_ignored_error(err):
        await log_ignored_error(err, clean_tb, label, extras)
        return

    caption = format_traceback(err, clean_tb, label, extras)
    if len(caption) > 4096:
        await send_large_error(clean_tb, caption.split("\n\n")[0], filename)
    else:
        try:
            await app.send_message(LOGGER_ID, caption)
        except Exception:
            pass

async def log_ignored_error(err, tb, label, extras=None):
    if not DEBUG_IGNORE_LOG:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"\n--- Ignored Error | {label} @ {timestamp} ---",
        f"Type: {type(err).__name__}",
        *(f"{key}: {val}" for key, val in (extras or {}).items()),
        "Traceback:",
        tb.strip(),
        "------------------------------------------\n"
    ]
    try:
        mode = "w" if (os.path.exists(DEBUG_LOG_FILE) and os.path.getsize(DEBUG_LOG_FILE) > MAX_DEBUG_LOG_BYTES) else "a"
        async with aiofiles.open(DEBUG_LOG_FILE, mode, encoding="utf-8") as log:
            await log.write("\n".join(lines))
    except OSError:
        pass



# ========== Decorators ==========


def capture_err(func):
    """
    Handles errors in command message handlers.
    Logs only unignored errors.
    """
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            try:
                await app.leave_chat(message.chat.id)
            except Exception:
                pass
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            chat_id = message.chat.id if getattr(message, "chat", None) else "inline"
            extras = {
                "User": message.from_user.first_name if getattr(message, "from_user", None) else "N/A",
                "Command": (message.text or message.caption or "")[:200],
                "Chat ID": chat_id
            }
            filename = f"error_log_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Error", filename, extras)
            raise err
    return wrapper


def capture_callback_err(func):
    """
    Handles errors in callback query handlers.
    Logs only unignored errors.
    """
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            msg = getattr(callback_query, "message", None)
            chat_id = msg.chat.id if (msg and getattr(msg, "chat", None)) else "inline"
            extras = {
                "User": callback_query.from_user.first_name if getattr(callback_query, "from_user", None) else "N/A",
                "Chat ID": chat_id
            }
            filename = f"cb_error_log_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Callback Error", filename, extras)
            raise err
    return wrapper

def capture_internal_err(func):
    """
    Handles errors in background/internal async bot functions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {"Function": func.__name__}
            filename = f"internal_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Internal Error", filename, extras)
            raise err
    return wrapper
