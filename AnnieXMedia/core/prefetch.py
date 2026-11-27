# Authored By Certified Coders © 2025
"""Background track pre-fetching (zero-gap queue transitions) and Smart Autoplay Radio."""
import asyncio
import os
import re
from collections import deque
from typing import Any, Deque, Dict, Optional

from youtubesearchpython.aio import VideosSearch

import config
from AnnieXMedia.core.track_cache import (
    download_from_tg_cache,
    find_local_media,
    is_valid_vidid,
)
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.misc import db
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.stream.queue import put_queue

log = LOGGER(__name__)

_CLEAN_TITLE_RE = re.compile(
    r"(\([^)]*(?:official|video|audio|lyric|lyrics|hd|4k|full|status|teaser)[^)]*\)|"
    r"\[[^\]]*(?:official|video|audio|lyric|lyrics|hd|4k|full)[^\]]*\]|"
    r"\b(?:official\s*(?:music)?\s*video|lyrical\s*video|full\s*song|hd|4k)\b)",
    re.IGNORECASE,
)
_NOISE_WORDS = ("reaction", "teaser", "trailer", "shorts", "whatsapp status", "ringtone")
_HISTORY_MAX = 30
_MAX_AUTOPLAY_CHATS = 1024

_recent_vidids: Dict[int, Deque[str]] = {}
_last_tracks: Dict[int, Dict[str, Any]] = {}
_prefetch_inflight: set[tuple[int, str]] = set()
_autoplay_locks: Dict[int, asyncio.Lock] = {}


def _autoplay_lock(chat_id: int) -> asyncio.Lock:
    lock = _autoplay_locks.get(chat_id)
    if lock is None:
        if len(_autoplay_locks) >= _MAX_AUTOPLAY_CHATS:
            for cid in list(_autoplay_locks.keys())[:256]:
                if not _autoplay_locks[cid].locked():
                    _autoplay_locks.pop(cid, None)
                    _recent_vidids.pop(cid, None)
                    _last_tracks.pop(cid, None)
        lock = asyncio.Lock()
        _autoplay_locks[chat_id] = lock
    return lock


def record_played_track(chat_id: int, track: Optional[Dict[str, Any]]) -> None:
    """Remember recently played tracks per chat so Smart Autoplay avoids repeats."""
    if not chat_id or not isinstance(track, dict):
        return
    vid = str(track.get("vidid") or "").strip()
    if len(_recent_vidids) >= _MAX_AUTOPLAY_CHATS and chat_id not in _recent_vidids:
        _recent_vidids.pop(next(iter(_recent_vidids)), None)
    hist = _recent_vidids.setdefault(chat_id, deque(maxlen=_HISTORY_MAX))
    if is_valid_vidid(vid) and vid not in hist:
        hist.append(vid)
    _last_tracks[chat_id] = {
        "vidid": vid,
        "title": str(track.get("title") or ""),
        "streamtype": str(track.get("streamtype") or "audio"),
        "chat_id": int(track.get("chat_id") or chat_id),
    }


def get_last_track(chat_id: int) -> Optional[Dict[str, Any]]:
    return _last_tracks.get(chat_id)


def clean_song_title(raw_title: str) -> str:
    cleaned = _CLEAN_TITLE_RE.sub(" ", str(raw_title or "")).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -|•")
    return cleaned[:90] or str(raw_title or "").strip()[:90]


async def _prefetch_worker(chat_id: int, vidid: str, item: Dict[str, Any]) -> None:
    key = (chat_id, vidid)
    try:
        from AnnieXMedia import YouTube

        is_video = str(item.get("streamtype") or "audio") == "video"
        title = str(item.get("title") or vidid)

        local = find_local_media(vidid, is_video=is_video)
        if not local:
            local = await download_from_tg_cache(vidid, is_video=is_video, title=title)
        if not local:
            local, direct = await YouTube.download(
                vidid, None, video=is_video, videoid=vidid, title=title
            )
            if not direct:
                local = None

        if local and os.path.isfile(local):
            queue = db.get(chat_id)
            if isinstance(queue, list):
                for entry in queue[1:]:
                    if isinstance(entry, dict) and entry.get("vidid") == vidid:
                        entry["prefetched_file"] = local
                        entry["file"] = local
                        if local not in config.autoclean:
                            config.autoclean.append(local)
                        log.info(f"⚡ Pre-fetched next track for {chat_id}: {title[:40]}")
                        break
    except Exception as exc:
        log.debug(f"Pre-fetch skipped for {vidid} in {chat_id}: {exc}")
    finally:
        _prefetch_inflight.discard(key)


def schedule_prefetch_next(chat_id: int) -> None:
    """Download the queued next track in the background before the current track finishes."""
    queue = db.get(chat_id)
    if not isinstance(queue, list) or len(queue) < 2:
        return
    nxt = queue[1]
    if not isinstance(nxt, dict):
        return
    vid = str(nxt.get("vidid") or "").strip()
    file_marker = str(nxt.get("file") or "")
    if not is_valid_vidid(vid) or nxt.get("prefetched_file") or "vid_" not in file_marker:
        return
    key = (chat_id, vid)
    if key in _prefetch_inflight:
        return
    _prefetch_inflight.add(key)
    try:
        asyncio.get_running_loop().create_task(_prefetch_worker(chat_id, vid, nxt))
    except RuntimeError:
        _prefetch_inflight.discard(key)


def _pick_autoplay_queries(title: str) -> list[str]:
    base = clean_song_title(title)
    if not base:
        return []
    queries: list[str] = []
    if " - " in base:
        artist = base.split(" - ", 1)[0].strip()
        if len(artist) >= 3:
            queries.append(f"{artist} hit songs audio")
    elif "|" in base:
        head = base.split("|", 1)[0].strip()
        if len(head) >= 3:
            queries.append(f"{head} related songs")
    queries.append(f"{base} similar songs mix")
    queries.append(f"{base} song")
    return queries


async def queue_smart_autoplay_track(
    chat_id: int, last_track: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Find and queue one similar non-duplicate track when a Voice Chat queue finishes."""
    async with _autoplay_lock(chat_id):
        ref = last_track or _last_tracks.get(chat_id)
        if not isinstance(ref, dict):
            return None
        last_title = str(ref.get("title") or "").strip()
        last_vid = str(ref.get("vidid") or "").strip()
        if not last_title and not is_valid_vidid(last_vid):
            return None
        if last_vid in ("telegram", "soundcloud", "live") or "index_" in str(ref.get("file") or ""):
            return None

        if not last_title and is_valid_vidid(last_vid):
            try:
                from AnnieXMedia import YouTube

                t = await YouTube.title(last_vid, videoid=True)
                last_title = str(t or "")
            except Exception:
                last_title = ""
        if not last_title:
            return None

        recent = set(_recent_vidids.get(chat_id) or ())
        if is_valid_vidid(last_vid):
            recent.add(last_vid)

        chosen = None
        for q in _pick_autoplay_queries(last_title):
            try:
                res = await asyncio.wait_for(VideosSearch(q, limit=10).next(), timeout=10.0)
                items = res.get("result") or []
            except Exception:
                continue
            for item in items:
                vid = str(item.get("id") or "").strip()
                if not is_valid_vidid(vid) or vid in recent:
                    continue
                cand_title = str(item.get("title") or "").strip()
                low_t = cand_title.lower()
                if any(w in low_t for w in _NOISE_WORDS):
                    continue
                dur_str = str(item.get("duration") or "").strip()
                if not dur_str or dur_str.lower() == "none":
                    continue
                try:
                    dur_sec = time_to_seconds(dur_str)
                except Exception:
                    continue
                if dur_sec < 45 or dur_sec > config.DURATION_LIMIT:
                    continue
                chosen = {
                    "vidid": vid,
                    "title": cand_title,
                    "duration": dur_str,
                }
                break
            if chosen:
                break

        if not chosen:
            return None

        cand_vid = chosen["vidid"]
        cand_title = chosen["title"]
        cand_dur = chosen["duration"]
        is_video = str(ref.get("streamtype") or "audio") == "video"
        orig_chat = int(ref.get("chat_id") or chat_id)

        hist = _recent_vidids.setdefault(chat_id, deque(maxlen=_HISTORY_MAX))
        hist.append(cand_vid)

        resolved_path = find_local_media(cand_vid, is_video=is_video)
        if not resolved_path:
            resolved_path = await download_from_tg_cache(cand_vid, is_video=is_video, title=cand_title)

        file_entry = resolved_path if resolved_path else f"vid_{cand_vid}"
        await put_queue(
            chat_id,
            orig_chat,
            file_entry,
            cand_title,
            cand_dur,
            "🎧 Autoplay Radio",
            cand_vid,
            0,
            "video" if is_video else "audio",
        )
        queue = db.get(chat_id)
        if isinstance(queue, list) and queue:
            queue[-1]["is_autoplay"] = True
            if resolved_path:
                queue[-1]["prefetched_file"] = resolved_path
            return queue[-1]
        return None
