# Authored By Certified Coders © 2025
import hashlib
import time
from pyrogram.types import InlineKeyboardButton
import config
from AnnieXMedia.utils.formatters import time_to_seconds

LAST_UPDATE_TIME = {}


def _slider_token(query: str) -> str:
    """Map arbitrary UTF-8 query to a short fixed ASCII key inside config.lyrical."""
    q = str(query or "")
    tok = "sl_" + hashlib.sha1(q.encode("utf-8", errors="ignore")).hexdigest()[:10]
    if len(config.lyrical) > 2048:
        for k in list(config.lyrical.keys())[:512]:
            if str(k).startswith("sl_"):
                config.lyrical.pop(k, None)
    config.lyrical[tok] = q
    return tok


def track_markup(_, videoid, user_id, channel, fplay):
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            )
        ],
    ]


def should_update_progress(chat_id):
    now = time.time()
    last = LAST_UPDATE_TIME.get(chat_id, 0)
    if now - last >= 6:
        if len(LAST_UPDATE_TIME) > 4096:
            cutoff = now - 300
            for k, ts in list(LAST_UPDATE_TIME.items()):
                if ts < cutoff:
                    LAST_UPDATE_TIME.pop(k, None)
        LAST_UPDATE_TIME[chat_id] = now
        return True
    return False


def generate_progress_bar(played_sec, duration_sec):
    if duration_sec <= 0:
        percentage = 0
    else:
        percentage = min(max((played_sec / duration_sec) * 100, 0), 100)

    bar_length = 8
    filled = max(0, min(bar_length, int(round(bar_length * percentage / 100))))
    return "▰" * filled + "▱" * (bar_length - filled)


def control_buttons(_, chat_id):
    return [[
        InlineKeyboardButton(text="▷", callback_data=f"stream_admin Resume|{chat_id}"),
        InlineKeyboardButton(text="II", callback_data=f"stream_admin Pause|{chat_id}"),
        InlineKeyboardButton(text="↻", callback_data=f"stream_admin Replay|{chat_id}"),
        InlineKeyboardButton(text="‣‣I", callback_data=f"stream_admin Skip|{chat_id}"),
        InlineKeyboardButton(text="▢", callback_data=f"stream_admin Stop|{chat_id}"),
    ]]


def stream_markup_timer(_, chat_id, played, dur):
    if not should_update_progress(chat_id):
        return None

    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    bar = generate_progress_bar(played_sec, duration_sec)

    return (
        [[InlineKeyboardButton(text=f"{played} {bar} {dur}", callback_data="GetTimer")]] +
        control_buttons(_, chat_id) +
        [[InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")]]
    )


def stream_markup(_, chat_id):
    return control_buttons(_, chat_id) + [[InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")]]


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"AnniePlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}"
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"AnniePlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            ),
        ],
    ]

    return buttons

def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}"
            )
        ],
    ]


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    q_tok = query if str(query).startswith("sl_") and len(str(query)) <= 16 else _slider_token(query)
    return [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{q_tok}|{user_id}|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {q_tok}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{q_tok}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
