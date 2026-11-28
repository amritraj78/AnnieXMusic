# Authored By Certified Coders © 2025
import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError, ConnectionNotFound
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup, LinkPreviewOptions
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from strings import get_string
from AnnieXMedia import LOGGER, YouTube, app
from AnnieXMedia.misc import db
from AnnieXMedia.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    is_autoplay,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from AnnieXMedia.core.prefetch import queue_smart_autoplay_track, record_played_track
from AnnieXMedia.core.security import redact_secrets
from AnnieXMedia.core.track_cache import is_valid_vidid
from AnnieXMedia.utils.exceptions import AssistantErr
from AnnieXMedia.utils.formatters import check_duration, seconds_to_min, speed_converter
from AnnieXMedia.utils.inline.play import stream_markup
from AnnieXMedia.utils.stream.autoclear import auto_clean
from AnnieXMedia.utils.thumbnails import get_thumb
from AnnieXMedia.utils.errors import capture_internal_err

autoend = {}
counter = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ffmpeg_params,
        )
    else:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.IGNORE,
            ffmpeg_parameters=ffmpeg_params,
        )

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    autoend.pop(chat_id, None)
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    """Manage assistant Pyrogram clients and PyTgCalls voice/video call sessions."""

    _CLIENT_SLOTS = (
        ("AnnieXAssis1", "userbot1", "one", "STRING1"),
        ("AnnieXAssis2", "userbot2", "two", "STRING2"),
        ("AnnieXAssis3", "userbot3", "three", "STRING3"),
        ("AnnieXAssis4", "userbot4", "four", "STRING4"),
        ("AnnieXAssis5", "userbot5", "five", "STRING5"),
    )

    def __init__(self):
        for _, ub_attr, call_attr, _ in self._CLIENT_SLOTS:
            setattr(self, ub_attr, None)
            setattr(self, call_attr, None)
        self._clients_built = False
        self.active_calls: set[int] = set()
        self._locks: dict[int, asyncio.Lock] = {}
        self._bg_tasks: set[asyncio.Task] = set()

    def _ensure_clients(self) -> None:
        if self._clients_built:
            return
        for session_name, ub_attr, call_attr, cfg_attr in self._CLIENT_SLOTS:
            raw_session = (getattr(config, cfg_attr, None) or "").strip()
            if raw_session and raw_session.lower() != "none":
                ub = Client(
                    session_name,
                    config.API_ID,
                    config.API_HASH,
                    session_string=raw_session,
                    no_updates=True,
                    workers=4,
                )
                setattr(self, ub_attr, ub)
                setattr(self, call_attr, PyTgCalls(ub, workers=4))
            else:
                setattr(self, ub_attr, None)
                setattr(self, call_attr, None)
        self._clients_built = True

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        lock = self._locks.get(chat_id)
        if lock is None:
            if len(self._locks) > 2048:
                for k in list(self._locks.keys()):
                    if not self._locks[k].locked() and k not in self.active_calls:
                        self._locks.pop(k, None)
            lock = asyncio.Lock()
            self._locks[chat_id] = lock
        return lock

    async def _abort_failed_track(self, client, chat_id: int, pop_front: bool = True) -> None:
        check = db.get(chat_id)
        if pop_front and check:
            popped = check.pop(0)
            await auto_clean(popped)
        if not db.get(chat_id):
            await _clear_(chat_id)
            autoend.pop(chat_id, None)
            if chat_id in self.active_calls:
                try:
                    await client.leave_call(chat_id)
                except Exception:
                    pass
                finally:
                    self.active_calls.discard(chat_id)
            return
        task = asyncio.create_task(self.play(client, chat_id))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)


    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            assistant = await group_assistant(self, chat_id)
            await _clear_(chat_id)
            if chat_id not in self.active_calls:
                return
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            assistant = await group_assistant(self, chat_id)
            try:
                check = db.get(chat_id)
                if check:
                    popped = check.pop(0)
                    if popped:
                        await auto_clean(popped)
            except (IndexError, KeyError):
                pass
            await _clear_(chat_id)
            if chat_id not in self.active_calls:
                return
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)

    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        async with self._lock_for(chat_id):
            assistant = await group_assistant(self, chat_id)
            stream = dynamic_media_stream(path=link, video=bool(video))
            await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Invalid stream info for speedup.")

        try:
            spd = float(speed)
        except (ValueError, TypeError):
            raise AssistantErr("Invalid speed value.")
        if not (0.5 <= spd <= 2.0):
            raise AssistantErr("Speed must be between 0.5x and 2.0x.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(spd))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)
        is_video = playing[0].get("streamtype") == "video"

        if not os.path.exists(out):
            part_out = f"{out}.part.{os.getpid()}"
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", file_path]
            if is_video:
                cmd.extend(["-filter:v", f"setpts={1.0 / spd:.4f}*PTS"])
            cmd.extend(["-filter:a", f"atempo={spd}", part_out])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                if os.path.exists(part_out):
                    os.remove(part_out)
                raise AssistantErr("Audio speed processing timed out.")

            if proc.returncode != 0 or not os.path.exists(part_out):
                if os.path.exists(part_out):
                    os.remove(part_out)
                err_txt = stderr.decode("utf-8", errors="ignore")[:200] if stderr else "Unknown ffmpeg error"
                raise AssistantErr(f"Speed conversion failed: {err_txt}")
            os.replace(part_out, out)

        dur_res = await asyncio.get_running_loop().run_in_executor(None, check_duration, out)
        try:
            dur = int(float(dur_res))
        except (ValueError, TypeError):
            dur = 0
        played, con_seconds = speed_converter(playing[0].get("played", 0), spd)
        duration_min = seconds_to_min(dur)
        ffmpeg_params = (
            f"-ss {played} -to {duration_min}"
            if duration_min not in ("-", "00:00") and played != "-"
            else None
        )
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
            db[chat_id][0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": spd,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            })
        else:
            raise AssistantErr("Stream mismatch during speedup.")


    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except Exception:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        async with self._lock_for(chat_id):
            assistant = await group_assistant(self, chat_id)
            lang = await get_lang(chat_id)
            _ = get_string(lang)
            stream = dynamic_media_stream(path=link, video=bool(video))

            try:
                await assistant.play(chat_id, stream)
            except (NoActiveGroupCall, ChatAdminRequired):
                raise AssistantErr(_["call_8"])
            except NoAudioSourceFound:
                raise AssistantErr(_["call_11"])
            except NoVideoSourceFound:
                raise AssistantErr(_["call_12"])
            except (ConnectionNotFound, TelegramServerError):
                raise AssistantErr(_["call_10"])
            except Exception as e:
                raise AssistantErr(
                    f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {e}"
                )
            self.active_calls.add(chat_id)
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if video:
                await add_active_video_chat(chat_id)

            if await is_autoend():
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)


    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        async with self._lock_for(chat_id):
            await self._play_unlocked(client, chat_id)

    async def _play_unlocked(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except Exception:
                        pass
                    finally:
                        self.active_calls.discard(chat_id)
                return

            prev_track = dict(check[0]) if isinstance(check[0], dict) else None
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)

            if popped:
                await auto_clean(popped)

            if not check and prev_track and await is_autoplay(chat_id):
                await queue_smart_autoplay_track(chat_id, prev_track)
                check = db.get(chat_id)

            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except Exception:
                        pass
                    finally:
                        self.active_calls.discard(chat_id)
                return
        except Exception:
            try:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    await client.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)
            return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            check[0]["played"] = 0
            record_played_track(chat_id, check[0])

            exis = (check[0]).get("old_dur")
            if exis:
                check[0]["dur"] = exis
                check[0]["seconds"] = check[0]["old_second"]
                check[0]["speed_path"] = None
                check[0]["speed"] = 1.0

            video = str(streamtype) == "video"

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0 or not link:
                    await app.send_message(original_chat_id, text=_["call_6"])
                    return await self._abort_failed_track(client, chat_id)

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    await app.send_message(original_chat_id, text=_["call_6"])
                    return await self._abort_failed_track(client, chat_id)

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                try:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                except Exception:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=video,
                        title=title,
                    )
                except Exception:
                    file_path, direct = None, None
                if not file_path:
                    try:
                        await mystic.edit_text(
                            _["call_6"], link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                    except Exception:
                        pass
                    return await self._abort_failed_track(client, chat_id)

                stream = dynamic_media_stream(path=file_path, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    try:
                        await mystic.edit_text(_["call_6"])
                    except Exception:
                        pass
                    return await self._abort_failed_track(client, chat_id)

                if direct and chat_id in db and db[chat_id]:
                    db[chat_id][0]["file"] = file_path

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                try:
                    await mystic.delete()
                except Exception:
                    pass
                try:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                except Exception:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                stream = dynamic_media_stream(path=videoid, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    await app.send_message(original_chat_id, text=_["call_6"])
                    return await self._abort_failed_track(client, chat_id)

                button = stream_markup(_, chat_id)
                try:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.STREAM_IMG_URL,
                        caption=_["stream_2"].format(user),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                except Exception:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_2"].format(user),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

            else:
                if (
                    not queued.startswith(("http://", "https://"))
                    and not os.path.exists(queued)
                    and is_valid_vidid(videoid)
                ):
                    fb_path, _ = await YouTube.download(
                        videoid, None, videoid=videoid, video=video, title=title
                    )
                    if fb_path:
                        queued = fb_path
                        check[0]["file"] = fb_path
                stream = dynamic_media_stream(path=queued, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    await app.send_message(original_chat_id, text=_["call_6"])
                    return await self._abort_failed_track(client, chat_id)

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=(
                                config.TELEGRAM_AUDIO_URL
                                if str(streamtype) == "audio"
                                else config.TELEGRAM_VIDEO_URL
                            ),
                            caption=_["stream_1"].format(
                                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except Exception:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=_["stream_1"].format(
                                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    if chat_id in db and db[chat_id]:
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.SOUNCLOUD_IMG_URL,
                            caption=_["stream_1"].format(
                                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except Exception:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=_["stream_1"].format(
                                config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    if chat_id in db and db[chat_id]:
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"

                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except FloodWait as e:
                        wait_s = min(int(e.value), 60)
                        LOGGER(__name__).warning(f"FloodWait: Sleeping for {wait_s}s (raw={e.value})")
                        await asyncio.sleep(wait_s)
                        try:
                            run = await app.send_photo(
                                chat_id=original_chat_id,
                                photo=img,
                                caption=_["stream_1"].format(
                                    f"https://t.me/{app.username}?start=info_{videoid}",
                                    title[:23],
                                    check[0]["dur"],
                                    user,
                                ),
                                reply_markup=InlineKeyboardMarkup(button),
                            )
                        except Exception:
                            run = await app.send_message(
                                chat_id=original_chat_id,
                                text=_["stream_1"].format(
                                    f"https://t.me/{app.username}?start=info_{videoid}",
                                    title[:23],
                                    check[0]["dur"],
                                    user,
                                ),
                                reply_markup=InlineKeyboardMarkup(button),
                            )
                    except Exception:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    if chat_id in db and db[chat_id]:
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"


    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        self._ensure_clients()
        for client in (self.one, self.two, self.three, self.four, self.five):
            if client:
                await client.start()

    async def stop(self) -> None:
        for client in (self.one, self.two, self.three, self.four, self.five):
            if client:
                try:
                    await client.stop()
                except Exception:
                    pass

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        for client in (self.one, self.two, self.three, self.four, self.five):
            if client:
                try:
                    pings.append(client.ping)
                except Exception:
                    pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, StreamEnded):
                    if update.stream_type in (StreamEnded.Type.AUDIO, StreamEnded.Type.VIDEO):
                        assistant = await group_assistant(self, update.chat_id)
                        await self.play(assistant, update.chat_id)
                elif isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        await self.stop_stream(update.chat_id)
                        return
            except Exception as exc:
                LOGGER(__name__).warning(
                    f"PyTgCalls update recovery for {getattr(update, 'chat_id', '?')}: {redact_secrets(str(exc))[:180]}"
                )

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)


StreamController = Call()
