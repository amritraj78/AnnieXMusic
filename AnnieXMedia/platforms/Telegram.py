# Authored By Certified Coders © 2025
import asyncio
import os
import time
from typing import Optional, Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Voice

import config
from AnnieXMedia import app
from AnnieXMedia.utils.formatters import (
    check_duration,
    convert_bytes,
    get_readable_time,
    seconds_to_min,
)
from AnnieXMedia.core.security import safe_path_under, sanitize_ext, sanitize_id_token


class TeleAPI:
    def __init__(self):
        self.chars_limit = 4096
        self.sleep = 5

    async def send_split_text(self, message, string: str) -> bool:
        n = self.chars_limit
        out = [string[i : i + n] for i in range(0, len(string), n)]
        for x in out[:3]:
            await message.reply_text(x, link_preview_options=LinkPreviewOptions(is_disabled=True))
        return True

    async def get_link(self, message):
        return message.link

    async def get_filename(self, file, audio: Union[bool, str] = None) -> str:
        try:
            file_name = getattr(file, "file_name", None)
            if not file_name:
                file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        except Exception:
            file_name = "ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ"
        return file_name

    async def get_duration(self, file_obj, file_path: Optional[str] = None) -> str:
        try:
            if hasattr(file_obj, "duration") and file_obj.duration:
                return seconds_to_min(file_obj.duration)
        except Exception:
            pass

        if file_path:
            try:
                dur = await asyncio.to_thread(check_duration, file_path)
                return seconds_to_min(dur)
            except Exception:
                pass

        return "Unknown"

    async def get_filepath(
        self,
        audio: Union[bool, str] = None,
        video: Union[bool, str] = None,
    ) -> str:
        base = os.path.realpath("downloads")
        os.makedirs(base, exist_ok=True)
        if audio:
            uid = sanitize_id_token(getattr(audio, "file_unique_id", None), f"aud_{int(time.time())}")
            ext = "ogg" if isinstance(audio, Voice) else sanitize_ext(
                getattr(audio, "file_name", None),
                allowed=("mp3", "m4a", "ogg", "opus", "wav", "flac", "aac", "webm", "mp4"),
                default="ogg",
            )
            target = safe_path_under(base, f"{uid}.{ext}")
            return str(target) if target else os.path.join(base, f"{uid}.ogg")
        if video:
            uid = sanitize_id_token(getattr(video, "file_unique_id", None), f"vid_{int(time.time())}")
            ext = sanitize_ext(
                getattr(video, "file_name", None),
                allowed=("mp4", "mkv", "webm", "mov", "avi"),
                default="mp4",
            )
            target = safe_path_under(base, f"{uid}.{ext}")
            return str(target) if target else os.path.join(base, f"{uid}.mp4")
        return os.path.join(base, f"{int(time.time())}.dat")

    async def download(self, _, message, mystic, fname: str) -> bool:
        if not _ or not isinstance(_, dict):
            _ = {
                "tg_1": "{0}\n\n**Total Size:** {1}\n**Completed:** {2}\n**Progress:** {3}%\n**Speed:** {4}/s\n**ETA:** {5}",
                "tg_2": "**Downloaded successfully in {0}!**",
                "tg_3": "**Failed to download media.**",
            }
        if not getattr(message, "reply_to_message", None):
            try:
                await mystic.edit_text(_["tg_3"])
            except Exception:
                pass
            return False

        lower = [0, 8, 17, 38, 64, 77, 96]
        higher = [5, 10, 20, 40, 66, 80, 99]
        checker = [5, 10, 20, 40, 66, 80, 99]
        speed_counter = {}

        if os.path.isfile(fname) and os.path.getsize(fname) > 1024:
            return True

        part_path = f"{fname}.part.{int(time.time())}"
        dl_succeeded = False

        async def down_load():
            nonlocal dl_succeeded

            async def progress(current, total):
                if current == total or total == 0:
                    return
                if message.id not in speed_counter:
                    speed_counter[message.id] = time.time()
                elapsed = max(time.time() - speed_counter[message.id], 1e-3)

                upl = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="ᴄᴀɴᴄᴇʟ", callback_data="stop_downloading")]]
                )

                percentage = current * 100 / total
                try:
                    speed = current / elapsed
                    eta_s = int((total - current) / max(speed, 1e-6))
                except Exception:
                    speed, eta_s = 0, 0

                eta = get_readable_time(eta_s) or "0 sᴇᴄᴏɴᴅs"
                total_size = convert_bytes(total)
                completed_size = convert_bytes(current)
                speed_h = convert_bytes(speed)
                percentage_i = int(percentage)

                for counter in range(7):
                    low, high, check = int(lower[counter]), int(higher[counter]), int(checker[counter])
                    if low < percentage_i <= high and high == check:
                        try:
                            await mystic.edit_text(
                                text=_["tg_1"].format(
                                    app.mention, total_size, completed_size, str(percentage)[:5], speed_h, eta
                                ),
                                reply_markup=upl,
                            )
                            checker[counter] = 100
                        except Exception:
                            pass

            speed_counter[message.id] = time.time()
            try:
                saved = await app.download_media(
                    message.reply_to_message,
                    file_name=part_path,
                    progress=progress,
                )
                if not saved or not os.path.isfile(saved) or os.path.getsize(saved) < 512:
                    try:
                        await mystic.edit_text(_["tg_3"])
                    except Exception:
                        pass
                    return
                os.replace(saved, fname)
                dl_succeeded = True
                try:
                    elapsed = get_readable_time(int(time.time() - speed_counter[message.id]))
                except Exception:
                    elapsed = "0 sᴇᴄᴏɴᴅs"
                try:
                    await mystic.edit_text(_["tg_2"].format(elapsed))
                except Exception:
                    pass
            except Exception:
                try:
                    await mystic.edit_text(_["tg_3"])
                except Exception:
                    pass

        task = asyncio.create_task(down_load())
        config.lyrical[mystic.id] = task
        try:
            await task
        except asyncio.CancelledError:
            return False
        finally:
            config.lyrical.pop(mystic.id, None)
            if not dl_succeeded and os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
        return dl_succeeded
