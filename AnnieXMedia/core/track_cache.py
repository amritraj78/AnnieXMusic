# Authored By Certified Coders © 2025
"""Telegram file_id + MongoDB persistent track cache for sub-second repeat playback."""
import asyncio
import contextlib
import os
import re
import time
from typing import Any, Dict, Optional

from pyrogram.errors import BadRequest, FloodWait

import config
from AnnieXMedia.core.dir import DOWNLOAD_DIR
from AnnieXMedia.core.mongo import mongodb
from AnnieXMedia.core.security import sanitize_ext
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.formatters import check_duration, seconds_to_min, time_to_seconds

log = LOGGER(__name__)

track_cachedb = mongodb.track_cache
_YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_MAX_TG_CACHE_BYTES = 49 * 1024 * 1024  # Keep safely under Bot API 50MB upload cap
_MEM_CACHE_MAX = 1024

_mem_cache: Dict[str, Dict[str, Any]] = {}
_pinned_paths: Dict[str, int] = {}
_tg_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_uploading_keys: set[str] = set()

stats: Dict[str, int] = {
    "disk_hits": 0,
    "tg_hits": 0,
    "uploads": 0,
    "misses": 0,
}


def _cache_key(vidid: str, is_video: bool) -> str:
    return f"{vidid}:{'video' if is_video else 'audio'}"


def is_valid_vidid(vidid: str) -> bool:
    return bool(vidid and _YOUTUBE_ID_RE.match(str(vidid).strip()))


def pin_path(path: str) -> None:
    if not path:
        return
    _pinned_paths[path] = _pinned_paths.get(path, 0) + 1


def unpin_path(path: str) -> bool:
    """Decrement pin refcount; return True if now unpinned (safe for caller cleanup)."""
    if not path:
        return True
    cur = _pinned_paths.get(path, 0)
    if cur <= 1:
        _pinned_paths.pop(path, None)
        return True
    _pinned_paths[path] = cur - 1
    return False


def is_path_pinned(path: str) -> bool:
    return bool(path and _pinned_paths.get(path, 0) > 0)


def _remember(key: str, doc: Dict[str, Any]) -> None:
    if len(_mem_cache) >= _MEM_CACHE_MAX:
        _mem_cache.pop(next(iter(_mem_cache)), None)
    _mem_cache[key] = doc


async def get_cached_track(vidid: str, is_video: bool = False) -> Optional[Dict[str, Any]]:
    """Look up Telegram file_id + duration metadata in memory, then MongoDB."""
    vid = str(vidid or "").strip()
    if not is_valid_vidid(vid):
        return None
    mode = "video" if is_video else "audio"
    key = _cache_key(vid, is_video)
    if cached := _mem_cache.get(key):
        return cached
    try:
        doc = await track_cachedb.find_one({"vidid": vid, "mode": mode})
    except Exception as exc:
        log.debug(f"track_cache lookup error for {vid}: {exc}")
        return None
    if doc and doc.get("file_id"):
        entry = {
            "vidid": vid,
            "mode": mode,
            "file_id": str(doc["file_id"]),
            "duration": str(doc.get("duration") or "0:00"),
            "seconds": int(doc.get("seconds") or 0),
            "title": str(doc.get("title") or vid),
            "ext": sanitize_ext(doc.get("ext") or ("mp4" if is_video else "webm")),
        }
        _remember(key, entry)
        return entry
    return None


async def _invalidate_cached_track(vidid: str, is_video: bool) -> None:
    key = _cache_key(vidid, is_video)
    _mem_cache.pop(key, None)
    mode = "video" if is_video else "audio"
    with contextlib.suppress(Exception):
        await track_cachedb.delete_one({"vidid": vidid, "mode": mode})


def find_local_media(vidid: str, is_video: bool = False) -> Optional[str]:
    if not is_valid_vidid(vidid):
        return None
    exts = ("mp4", "mkv", "webm") if is_video else ("mp3", "m4a", "webm", "ogg", "mp4", "mkv")
    for ext in exts:
        path = os.path.join(DOWNLOAD_DIR, f"{vidid}.{ext}")
        try:
            if os.path.isfile(path) and os.path.getsize(path) >= 2048:
                return path
        except OSError:
            continue
    return None


async def download_from_tg_cache(vidid: str, is_video: bool = False, title: str = "") -> Optional[str]:
    """Fetch cached track directly from Telegram CDN by file_id, bypassing yt-dlp & ffmpeg."""
    vid = str(vidid or "").strip()
    if not is_valid_vidid(vid):
        return None

    if local := find_local_media(vid, is_video=is_video):
        stats["disk_hits"] += 1
        return local

    doc = await get_cached_track(vid, is_video=is_video)
    if not doc:
        return None

    from AnnieXMedia import app

    if not getattr(app, "id", 0) or not getattr(app, "is_connected", False):
        return None

    key = _cache_key(vid, is_video)
    existing_fut: Optional[asyncio.Future] = None
    async with _inflight_lock:
        if key in _tg_inflight:
            existing_fut = _tg_inflight[key]
        else:
            fut = asyncio.get_running_loop().create_future()
            _tg_inflight[key] = fut

    if existing_fut is not None:
        try:
            return await existing_fut
        except asyncio.CancelledError:
            raise
        except Exception:
            return None

    result_path: Optional[str] = None
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        ext = sanitize_ext(doc.get("ext") or ("mp4" if is_video else "webm"))
        if ext == "bin":
            ext = "mp4" if is_video else "webm"
        final_path = os.path.join(DOWNLOAD_DIR, f"{vid}.{ext}")
        part_path = f"{final_path}.tgpart"
        dl = await asyncio.wait_for(
            app.download_media(doc["file_id"], file_name=part_path),
            timeout=35.0,
        )
        if dl and os.path.isfile(dl) and os.path.getsize(dl) >= 2048:
            os.replace(dl, final_path)
            result_path = final_path
            stats["tg_hits"] += 1
            log.info(f"⚡ Telegram Cache Hit [{doc.get('title') or title or vid}] ({vid})")
        else:
            with contextlib.suppress(OSError):
                if dl and os.path.isfile(dl):
                    os.remove(dl)
    except BadRequest as exc:
        log.warning(f"Invalid cached file_id for {vid}, purging stale cache: {exc}")
        await _invalidate_cached_track(vid, is_video)
    except Exception as exc:
        log.debug(f"Telegram cache download skipped for {vid}: {exc}")
    finally:
        part_cleanup = os.path.join(
            DOWNLOAD_DIR, f"{vid}.{sanitize_ext(doc.get('ext') or ('mp4' if is_video else 'webm'))}.tgpart"
        )
        with contextlib.suppress(OSError):
            if os.path.isfile(part_cleanup):
                os.remove(part_cleanup)
        if not fut.done():
            fut.set_result(result_path)
        async with _inflight_lock:
            _tg_inflight.pop(key, None)

    return result_path


async def _resolve_duration(file_path: str, duration_min: str, duration_sec: int) -> tuple[str, int]:
    sec = int(duration_sec or 0)
    dmin = str(duration_min or "").strip()
    if sec <= 0 and dmin and ":" in dmin:
        with contextlib.suppress(Exception):
            sec = max(int(time_to_seconds(dmin)), 0)
    if sec <= 0 and os.path.isfile(file_path):
        with contextlib.suppress(Exception):
            raw = await asyncio.to_thread(check_duration, file_path)
            sec = max(int(float(raw or 0)), 0)
    if (not dmin or dmin == "None") and sec > 0:
        dmin = seconds_to_min(sec)
    return (dmin or "0:00", sec)


async def _upload_worker(
    vid: str,
    file_path: str,
    title: str,
    duration_min: str,
    duration_sec: int,
    is_video: bool,
) -> None:
    key = _cache_key(vid, is_video)
    mode = "video" if is_video else "audio"
    try:
        from AnnieXMedia import app

        if not getattr(app, "id", 0) or not getattr(app, "is_connected", False):
            return
        if not config.LOGGER_ID:
            return
        if await get_cached_track(vid, is_video=is_video):
            return
        if not os.path.isfile(file_path):
            return
        size = os.path.getsize(file_path)
        if size <= 2048 or size > _MAX_TG_CACHE_BYTES:
            return

        dmin, sec = await _resolve_duration(file_path, duration_min, duration_sec)
        clean_title = (str(title or vid).strip() or vid)[:100]
        ext = sanitize_ext(os.path.splitext(file_path)[1].lstrip(".") or ("mp4" if is_video else "webm"))
        if ext == "bin":
            ext = "mp4" if is_video else "webm"
        caption = f"💾 Cache [{mode.upper()}] | {clean_title}\nID: {vid} • {dmin}"

        async def _send():
            if is_video:
                return await app.send_video(
                    config.LOGGER_ID,
                    video=file_path,
                    caption=caption,
                    duration=sec or 0,
                    supports_streaming=True,
                    disable_notification=True,
                )
            return await app.send_audio(
                config.LOGGER_ID,
                audio=file_path,
                caption=caption,
                title=clean_title,
                duration=sec or 0,
                disable_notification=True,
            )

        try:
            sent = await _send()
        except FloodWait as e:
            await asyncio.sleep(min(int(e.value), 30))
            sent = await _send()

        media = getattr(sent, "video", None) if is_video else (getattr(sent, "audio", None) or getattr(sent, "document", None))
        file_id = getattr(media, "file_id", None) if media else None
        if not file_id:
            return

        doc = {
            "vidid": vid,
            "mode": mode,
            "file_id": str(file_id),
            "duration": dmin,
            "seconds": sec,
            "title": clean_title,
            "ext": ext,
            "updated_at": int(time.time()),
        }
        await track_cachedb.update_one(
            {"vidid": vid, "mode": mode},
            {"$set": doc},
            upsert=True,
        )
        _remember(key, doc)
        stats["uploads"] += 1
        log.info(f"💾 Cached track to Telegram/MongoDB: {clean_title} ({vid}, {dmin})")
    except Exception as exc:
        log.debug(f"Track cache upload skipped for {vid}: {exc}")
    finally:
        _uploading_keys.discard(key)
        unpin_path(file_path)


def schedule_cache_upload(
    vidid: str,
    file_path: str,
    title: str = "",
    duration_min: str = "",
    duration_sec: int = 0,
    is_video: bool = False,
) -> None:
    """Queue a non-blocking background upload to cache file_id in Telegram + MongoDB."""
    vid = str(vidid or "").strip()
    if not is_valid_vidid(vid) or not file_path or not os.path.isfile(file_path):
        return
    key = _cache_key(vid, is_video)
    if key in _uploading_keys or key in _mem_cache:
        return
    try:
        size = os.path.getsize(file_path)
        if size <= 2048 or size > _MAX_TG_CACHE_BYTES:
            return
    except OSError:
        return

    _uploading_keys.add(key)
    pin_path(file_path)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_upload_worker(vid, file_path, title, duration_min, duration_sec, is_video))
    except RuntimeError:
        _uploading_keys.discard(key)
        unpin_path(file_path)
