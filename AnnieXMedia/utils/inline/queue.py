# Authored By Certified Coders © 2025
from typing import Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def queue_markup(
    _,
    DURATION,
    CPLAY,
    videoid,
    played: Union[bool, int] = None,
    dur: Union[bool, int] = None,
):
    safe_vid = str(videoid)
    if len(safe_vid.encode("utf-8", errors="ignore")) > 40 or "://" in safe_vid:
        safe_vid = "index"

    not_dur = [
        [
            InlineKeyboardButton(
                text=_["QU_B_1"],
                callback_data=f"GetQueued {CPLAY}|{safe_vid}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
            ),
        ]
    ]
    with_dur = [
        [
            InlineKeyboardButton(
                text=_["QU_B_2"].format(played, dur),
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["QU_B_1"],
                callback_data=f"GetQueued {CPLAY}|{safe_vid}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data="close",
            ),
        ],
    ]
    return InlineKeyboardMarkup(not_dur if DURATION == "Unknown" else with_dur)


def queue_back_markup(_, CPLAY):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=_["BACK_BUTTON"],
                    callback_data=f"queue_back_timer {CPLAY}",
                ),
                InlineKeyboardButton(
                    text=_["CLOSE_BUTTON"],
                    callback_data="close",
                ),
            ]
        ]
    )


def aq_markup(_, chat_id):
    return [
        [
            InlineKeyboardButton(text="▷", callback_data=f"stream_admin Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"stream_admin Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"stream_admin Skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"stream_admin Stop|{chat_id}"),
        ],
        [InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")],
    ]
