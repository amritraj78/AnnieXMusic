# Authored By Certified Coders © 2025
import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Playlist

from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.core.security import is_safe_http_url
from AnnieXMedia.core.self_heal import note_download_failure, reset_download_failures
from AnnieXMedia.core.track_cache import (
    download_from_tg_cache,
    is_valid_vidid,
    schedule_cache_upload,
)
from AnnieXMedia.utils.cookie_handler import get_valid_cookie_file
from AnnieXMedia.utils.database import is_on_off
from AnnieXMedia.utils.downloader import extract_video_id, yt_dlp_download
from AnnieXMedia.utils.errors import capture_internal_err
from AnnieXMedia.utils.formatters import time_to_seconds
from AnnieXMedia.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL


# === Caches ===
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()


# === Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


# === Helpers ===
def _cookiefile_path() -> Optional[str]:
    return get_valid_cookie_file()


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        return b"", b"timeout"
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        raise


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# === Main Class ===
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(
            r"^https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/", re.I
        )

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        s = (link or "").strip()
        if isinstance(videoid, str) and videoid.strip():
            vid = extract_video_id(videoid.strip()) or videoid.strip()
            s = self.base_url + vid if YOUTUBE_ID_RE.match(vid) else vid
        elif videoid is True and YOUTUBE_ID_RE.match(s):
            s = self.base_url + s

        low = s.lower()
        if "youtu.be/" in low:
            tail = s.split("/")[-1].split("?")[0]
            if YOUTUBE_ID_RE.match(tail):
                return self.base_url + tail
        elif "youtube.com/shorts/" in low or "youtube.com/live/" in low:
            tail = s.split("/")[-1].split("?")[0]
            if YOUTUBE_ID_RE.match(tail):
                return self.base_url + tail

        return s.split("&")[0] if "watch?v=" in low else s

    # === URL Handling ===
    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    async def _ensure_watch_url(self, maybe_query_or_url: str) -> Optional[str]:
        prepared = self._prepare_link(maybe_query_or_url)
        if prepared.startswith("http"):
            return prepared
        data = await cached_youtube_search(prepared)
        if not data:
            return None
        vid = data[0].get("id")
        return self.base_url + vid if vid else None

    # === Metadata Fetching ===
    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        if not await self.exists(prepared) or not await is_safe_http_url(prepared):
            return False
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", "--", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode("utf-8", errors="replace"))
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError("No results from youtubesearchpython (VideosSearch)")
        except Exception as search_err:
            raise ValueError("Video not found", {"cause": str(search_err)}) from search_err

        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0] if info else ""

    async def _fetch_oembed_info(self, url: str) -> Optional[Dict]:
        try:
            session = await get_http_session()
            async with session.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and data.get("title"):
                        return data
        except Exception:
            pass
        return None

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)

        try:
            info = await self._fetch_video_info(prepared_link)
            if not info:
                raise ValueError(
                    f"No results from youtubesearchpython (VideosSearch) "
                    f"for query/URL: '{prepared_link}'"
                )
        except Exception as search_err:
            oembed = await self._fetch_oembed_info(prepared_link) if prepared_link.startswith("http") else None
            if oembed:
                search_res = await cached_youtube_search(oembed["title"])
                if search_res:
                    info = search_res[0]
                else:
                    vid = extract_video_id(prepared_link)
                    info = {
                        "id": vid,
                        "title": oembed["title"],
                        "webpage_url": prepared_link,
                        "duration": None,
                        "thumbnail": oembed.get("thumbnail_url", ""),
                    }
            else:
                if not await self.exists(prepared_link) or not await is_safe_http_url(prepared_link):
                    raise ValueError(
                        f"Unsupported or invalid YouTube target: '{prepared_link[:80]}'"
                    )
                stdout, stderr = await _exec_proc(
                    "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", "--", prepared_link
                )

                def _both_failed(details: str) -> ValueError:
                    return ValueError(
                        f"Both methods failed for '{prepared_link}':\n"
                        f"  1. youtubesearchpython error: {search_err}\n"
                        f"{details}"
                    )

                if not stdout:
                    stderr_msg = stderr.decode("utf-8", errors="replace").strip() if stderr else "Empty response"
                    raise _both_failed(f"  2. yt-dlp error: {stderr_msg[:300]}")

                try:
                    info = json.loads(stdout.decode("utf-8", errors="replace"))
                except json.JSONDecodeError as json_err:
                    raw = stdout.decode("utf-8", errors="replace")[:400]
                    raise _both_failed(
                        f"  2. yt-dlp JSON error: {json_err}\n"
                        f"     Raw: {raw}..."
                    ) from json_err

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", prepared_link),
            "vidid": info.get("id", ""),
            "duration_min": (
                info.get("duration")
                if isinstance(info.get("duration"), str)
                else None
            ),
            "thumb": thumb,
        }
        return details, info.get("id", "")

    # === Media & Formats ===
    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        if not await self.exists(link) or not await is_safe_http_url(link):
            return 0, "Invalid YouTube URL"
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            "--",
            link,
        )
        return (
            (1, stdout.decode("utf-8", errors="replace").split("\n")[0])
            if stdout
            else (0, stderr.decode("utf-8", errors="replace")[:300])
        )

    @capture_internal_err
    async def playlist(
        self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None
    ) -> List[str]:
        raw = (link or "").strip()
        if isinstance(videoid, str) and videoid.strip():
            raw = self.playlist_url + videoid.strip()
        elif videoid is True and raw and not raw.startswith("http"):
            raw = self.playlist_url + raw
        elif "list=" in raw:
            list_id = raw.split("list=", 1)[1].split("&", 1)[0]
            if list_id:
                raw = self.playlist_url + list_id
        if not await self.exists(raw) or not await is_safe_http_url(raw):
            return []

        try:
            plist = await Playlist.get(raw)
            items = [video.get("id") for video in plist.get("videos", [])[:limit] if video.get("id")]
            if items:
                return items
        except Exception:
            pass

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            "--",
            raw,
        )
        items = stdout.decode("utf-8", errors="replace").strip().split("\n") if stdout else []
        return [i for i in items if i]

    @capture_internal_err
    async def formats(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        if not await self.exists(link) or not await is_safe_http_url(link):
            return [], link
        key = f"f:{link}"
        now = time.time()

        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        opts = {"quiet": True, "socket_timeout": 12}
        if cf := _cookiefile_path():
            opts["cookiefile"] = cf

        def _extract_sync():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(link, download=False)
            except Exception:
                return None

        out: List[Dict] = []
        try:
            info = await asyncio.wait_for(asyncio.to_thread(_extract_sync), timeout=20.0)
            if info:
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append(
                        {
                            "format": fmt["format"],
                            "filesize": size,
                            "format_id": fmt["format_id"],
                            "ext": fmt["ext"],
                            "format_note": fmt["format_note"],
                            "yturl": link,
                        }
                    )
        except Exception:
            pass

        if out:
            async with _formats_lock:
                if len(_formats_cache) > YOUTUBE_META_MAX:
                    _formats_cache.clear()
                _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(
        self, link: str, query_type: int, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(
                f"Query type index {query_type} out of range (found {len(results)} results)"
            )
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[-1].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    async def _resolve_title(self, link: str, provided_title: Optional[str] = None) -> str:
        if provided_title and str(provided_title).strip():
            return str(provided_title).strip()
        if t := await self.title(link):
            return t
        if oembed := await self._fetch_oembed_info(link):
            return str(oembed.get("title") or "").strip()
        return ""

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        title: Optional[str] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)
        vid = extract_video_id(link)
        is_video = bool(video)

        # Serve from local disk or Telegram file_id cache (< 1s) before any YouTube lookup
        if is_valid_vidid(vid):
            cached_path = await download_from_tg_cache(vid, is_video=is_video, title=str(title or ""))
            if cached_path:
                reset_download_failures()
                return cached_path, True

        resolved_title = await self._resolve_title(link, title)

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                return None, None

            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=resolved_title)
                if p:
                    reset_download_failures()
                    schedule_cache_upload(vid, p, title=resolved_title, is_video=True)
                    return p, True
                note_download_failure()
                return None, None

            if await self.exists(link) and await is_safe_http_url(link):
                stdout, _ = await _exec_proc(
                    "yt-dlp",
                    *(_cookies_args()),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    "--",
                    link,
                )
                if stdout:
                    return stdout.decode("utf-8", errors="replace").split("\n")[0], None
            p = await yt_dlp_download(link, type="video", title=resolved_title)
            if p:
                reset_download_failures()
                schedule_cache_upload(vid, p, title=resolved_title, is_video=True)
                return p, True
            note_download_failure()
            return None, None

        p = await yt_dlp_download(link, type="audio", title=resolved_title)
        if p:
            reset_download_failures()
            schedule_cache_upload(vid, p, title=resolved_title, is_video=False)
            return p, True
        note_download_failure()
        return None, None
