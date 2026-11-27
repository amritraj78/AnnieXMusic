# Authored By Certified Coders © 2025
import asyncio
import contextlib
import glob
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import aiofiles
import aiohttp
from aiohttp import TCPConnector
from yt_dlp import YoutubeDL

from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.utils.cookie_handler import get_valid_cookie_file
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def log_download_source(title: str, source: str) -> None:
    LOGGER.info(f"Track '{title}' - Downloaded by {source}")


def extract_video_id(link: str) -> str:
    if not link:
        return ""
    s = link.strip()
    if YOUTUBE_ID_RE.match(s):
        return s
    low = s.lower()
    if "youtube.com" not in low and "youtu.be" not in low:
        return ""
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    if YOUTUBE_ID_RE.match(last):
        return last
    return ""


def get_cookie_file() -> Optional[str]:
    return get_valid_cookie_file()


def find_cached_file(video_id: str, media_type: str = "audio") -> Optional[str]:
    if not video_id:
        return None
    exts = ("mp4", "mkv", "webm") if media_type == "video" else ("mp3", "m4a", "webm", "mp4", "mkv")
    for ext in exts:
        path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


def get_ytdlp_base_opts() -> Dict[str, object]:
    opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": 1 << 20,
        "socket_timeout": 15,
        "retries": 1,
        "fragment_retries": 1,
        "cachedir": str(CACHE_DIR),
        "ignoreerrors": False,
        "merge_output_format": "mp4",
    }
    if cookiefile := get_cookie_file():
        opts["cookiefile"] = cookiefile
    return opts


async def get_http_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    async with _session_lock:
        if _session and not _session.closed:
            return _session
        timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
        connector = TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return _session


async def close_http_session() -> None:
    global _session
    async with _session_lock:
        if _session and not _session.closed:
            await _session.close()
        _session = None


async def download_file(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        session = await get_http_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    await f.write(chunk)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        return None


async def api_download_audio(link: str) -> Optional[str]:
    if not USE_AUDIO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{API_URL}/song/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        retries = 0
        while retries < 45:
            retries += 1
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                try:
                    data = await r.json()
                except Exception:
                    return None
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "webm")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
        return None
    except Exception:
        return None


async def api_download_video(link: str) -> Optional[str]:
    if not USE_VIDEO_API:
        return None
    vid = extract_video_id(link)
    if not vid:
        return None
    poll_url = f"{VIDEO_API_URL}/video/{vid}?api={API_KEY}"
    try:
        session = await get_http_session()
        retries = 0
        while retries < 45:
            retries += 1
            async with session.get(poll_url) as r:
                if r.status != 200:
                    return None
                try:
                    data = await r.json()
                except Exception:
                    return None
                status = str(data.get("status", "")).lower()
                if status == "downloading":
                    await asyncio.sleep(1.0)
                    continue
                if status != "done":
                    return None
                dl_url = data.get("link")
                fmt = data.get("format", "mp4")
                out_path = f"{DOWNLOAD_DIR}/{vid}.{fmt}"
                return await download_file(dl_url, out_path)
        return None
    except Exception:
        return None


def get_final_path_from_info(info: Optional[Dict], vid_override: Optional[str] = None) -> Optional[str]:
    if not isinstance(info, dict):
        return None
    vid = vid_override or info.get("id")
    if not vid:
        return None
    ext = info.get("ext")
    if ext:
        p = f"{DOWNLOAD_DIR}/{vid}.{ext}"
        if os.path.exists(p):
            return p
    matches = sorted(
        glob.glob(f"{DOWNLOAD_DIR}/{vid}.*"),
        key=os.path.getmtime,
        reverse=True,
    )
    return matches[0] if matches else None


_NOISE_BRACKETS_RE = re.compile(
    r"[\(\[][^\)\]]*(official|lyrical?|video|audio|full\s+song|4k|hd|uhd|hq|mv|visualizer|status)[^\)\]]*[\)\]]",
    re.I,
)
_NOISE_WORDS_RE = re.compile(
    r"\b(official(\s+music)?(\s+video)?|lyrical|lyric\s*video|lyrics|full\s*(song|video|audio)|music\s*video|video\s*song|audio\s*song|4k|uhd|full\s*hd|t-series|zee\s*music(\s*company)?|yrf|sony\s*music(\s*india)?|tips\s*official|speed\s*records|vevo)\b",
    re.I,
)
_VARIANT_TOKENS = {
    "cover", "karaoke", "instrumental", "remix", "lofi", "lo-fi",
    "slowed", "reverb", "nightcore", "8d", "mashup", "sped",
    "ringtone", "reaction", "teaser", "trailer", "tutorial", "dj",
}
_AUDIUS_API = "https://api.audius.co"


def _strip_noise(text: str) -> str:
    cleaned = _NOISE_BRACKETS_RE.sub(" ", text or "")
    cleaned = _NOISE_WORDS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[\(\)\[\]{}]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -|•,./")


def _build_search_queries(raw_title: str) -> List[str]:
    """Produce concise, ranked music queries from noisy YouTube video titles."""
    if not raw_title or not raw_title.strip():
        return []
    parts = [_strip_noise(p) for p in re.split(r"[|•]|//", raw_title) if _strip_noise(p)]
    candidates: List[str] = []
    if len(parts) >= 2:
        p0_words = parts[0].split()
        p1_words = parts[1].split()
        if len(p0_words) + len(p1_words) <= 8:
            candidates.append(f"{parts[0]} {parts[1]}")
    if parts:
        candidates.append(" ".join(parts[0].split()[:7]))
        if " - " in parts[0]:
            right = parts[0].split(" - ", 1)[1].strip()
            if right:
                candidates.append(right)
    else:
        cleaned = _strip_noise(raw_title)
        if cleaned:
            candidates.append(" ".join(cleaned.split()[:7]))

    seen = set()
    unique: List[str] = []
    for q in candidates:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q.strip())
    return unique


def _tokenize_alnum(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _score_track_candidate(
    query: str,
    raw_title: str,
    cand_title: str,
    duration: int,
    artist: str = "",
) -> float:
    if duration < 15:
        return -999.0
    q_tokens = _tokenize_alnum(query)
    raw_tokens = _tokenize_alnum(raw_title)
    cand_tokens = _tokenize_alnum(f"{cand_title} {artist}")
    if not q_tokens:
        return 0.0

    overlap = len(q_tokens & cand_tokens) / max(len(q_tokens), 1)
    score = overlap * 3.0
    if query.lower() in (cand_title or "").lower():
        score += 2.0
    if duration >= 60:
        score += 0.5
    elif duration < 45:
        score -= 2.5

    for vt in _VARIANT_TOKENS:
        if vt in cand_tokens and vt not in raw_tokens:
            score -= 3.5
    return score


async def _search_audius_best(queries: List[str], raw_title: str) -> Optional[Tuple[float, Dict]]:
    session = await get_http_session()
    best: Optional[Tuple[float, Dict]] = None

    for q in queries[:2]:
        try:
            async with session.get(
                f"{_AUDIUS_API}/v1/tracks/search",
                params={"query": q, "app_name": "AnnieXMusic"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    continue
                payload = await resp.json(content_type=None)
        except Exception:
            continue

        tracks = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(tracks, list):
            continue

        for track in tracks[:10]:
            if not isinstance(track, dict) or track.get("is_streamable") is False:
                continue
            tid = track.get("id")
            if not tid:
                continue
            try:
                dur = int(track.get("duration") or 0)
            except (ValueError, TypeError):
                dur = 0
            title = str(track.get("title") or "")
            artist = str((track.get("user") or {}).get("name") or "")
            sc = _score_track_candidate(q, raw_title, title, dur, artist)
            if best is None or sc > best[0]:
                best = (sc, track)

        if best and best[0] >= 2.0:
            break

    return best


async def _download_audius_track(vid: str, track: Dict) -> Optional[str]:
    tid = track.get("id")
    if not tid:
        return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out_path = f"{DOWNLOAD_DIR}/{vid}.mp3"
    part_path = f"{out_path}.part"
    stream_url = f"{_AUDIUS_API}/v1/tracks/{tid}/stream?app_name=AnnieXMusic"

    try:
        session = await get_http_session()
        async with session.get(
            stream_url,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            if resp.status != 200:
                return None
            total = 0
            async with aiofiles.open(part_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    total += len(chunk)
                    await f.write(chunk)
        if total < 16384:
            with contextlib.suppress(OSError):
                os.remove(part_path)
            return None
        os.replace(part_path, out_path)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        with contextlib.suppress(OSError):
            if os.path.exists(part_path):
                os.remove(part_path)
        return None


def _is_sc_full_track(entry: Dict) -> bool:
    if not isinstance(entry, dict) or not entry.get("webpage_url"):
        return False
    try:
        dur = int(entry.get("duration") or 0)
    except (ValueError, TypeError):
        dur = 0
    if dur <= 35:
        return False
    formats = entry.get("formats") or []
    if not formats:
        return True
    return any(
        "preview" not in str(f.get("format_id", "")).lower()
        and "/preview/" not in str(f.get("url", ""))
        for f in formats
    )


def _soundcloud_fallback_sync(vid: str, queries: List[str], raw_title: str) -> Optional[str]:
    search_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "extract_flat": False,
        "ignoreerrors": True,
        "socket_timeout": 12,
    }
    best: Optional[Tuple[float, str]] = None

    for q in queries[:2]:
        try:
            with YoutubeDL(search_opts) as ydl:
                res = ydl.extract_info(f"scsearch5:{q}", download=False)
        except Exception:
            continue
        entries = (res or {}).get("entries") or []
        for entry in entries:
            if not _is_sc_full_track(entry):
                continue
            try:
                dur = int(entry.get("duration") or 0)
            except (ValueError, TypeError):
                dur = 0
            sc = _score_track_candidate(
                q,
                raw_title,
                str(entry.get("title") or ""),
                dur,
                str(entry.get("uploader") or ""),
            )
            if best is None or sc > best[0]:
                best = (sc, str(entry["webpage_url"]))
        if best and best[0] >= 2.0:
            break

    if not best or best[0] < 0.0:
        return None

    dl_opts = get_ytdlp_base_opts()
    dl_opts.pop("cookiefile", None)
    dl_opts["outtmpl"] = f"{DOWNLOAD_DIR}/{vid}.%(ext)s"
    dl_opts["format"] = "bestaudio/best"
    try:
        with YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(best[1], download=True)
            return get_final_path_from_info(info, vid_override=vid)
    except Exception as e:
        LOGGER.warning(f"SoundCloud fallback download error for {vid}: {e}")
        return None


def _dailymotion_video_fallback_sync(vid: str, queries: List[str], raw_title: str) -> Optional[str]:
    search_opts = {
        "quiet": True,
        "no_warnings": True,
        "playlistend": 3,
        "ignoreerrors": True,
        "socket_timeout": 12,
    }
    best: Optional[Tuple[float, str]] = None

    for q in queries[:2]:
        search_url = f"https://www.dailymotion.com/search/{quote(q)}/videos"
        try:
            with YoutubeDL(search_opts) as ydl:
                res = ydl.extract_info(search_url, download=False)
        except Exception:
            continue
        entries = (res or {}).get("entries") or []
        for entry in entries:
            if not isinstance(entry, dict) or not (entry.get("webpage_url") or entry.get("url")):
                continue
            try:
                dur = int(entry.get("duration") or 0)
            except (ValueError, TypeError):
                dur = 0
            sc = _score_track_candidate(q, raw_title, str(entry.get("title") or ""), dur)
            if best is None or sc > best[0]:
                best = (sc, str(entry.get("webpage_url") or entry.get("url")))
        if best and best[0] >= 1.5:
            break

    if not best or best[0] < 0.0:
        return None

    dl_opts = get_ytdlp_base_opts()
    dl_opts.pop("cookiefile", None)
    dl_opts["outtmpl"] = f"{DOWNLOAD_DIR}/{vid}.%(ext)s"
    dl_opts["format"] = "best[height<=?720][width<=?1280]/bestvideo[height<=?720]+bestaudio/best"
    try:
        with YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(best[1], download=True)
            return get_final_path_from_info(info, vid_override=vid)
    except Exception as e:
        LOGGER.warning(f"Dailymotion video fallback error for {vid}: {e}")
        return None


async def _fallback_download_audio(vid: str, title: str) -> Optional[Tuple[str, str]]:
    queries = _build_search_queries(title)
    if not queries or not vid:
        return None

    audius_best = await _search_audius_best(queries, title)
    if audius_best and audius_best[0] >= 2.0:
        if path := await _download_audius_track(vid, audius_best[1]):
            return path, "Audius"

    loop = asyncio.get_running_loop()
    sc_path = await run_with_semaphore(
        loop.run_in_executor(None, _soundcloud_fallback_sync, vid, queries, title)
    )
    if sc_path:
        return sc_path, "SoundCloud-Search"

    if audius_best and audius_best[0] >= 0.0:
        if path := await _download_audius_track(vid, audius_best[1]):
            return path, "Audius"

    return None


def download_with_ytdlp_sync(link: str, fmt: str) -> Optional[str]:
    base_opts = get_ytdlp_base_opts()
    has_cookies = "cookiefile" in base_opts
    client_profiles = (
        [None, ["web", "tv"]]
        if has_cookies
        else [None, ["android_vr", "tv_simply"]]
    )

    last_err: Optional[Exception] = None
    for players in client_profiles:
        opts = dict(base_opts)
        opts["format"] = fmt
        if players:
            opts["extractor_args"] = {"youtube": {"player_client": players}}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                path = get_final_path_from_info(info)
                if path:
                    return path
        except Exception as e:
            last_err = e

    LOGGER.warning(
        f"yt-dlp download error for {link}: {last_err or 'no downloadable format found'}"
    )
    return None


async def run_with_semaphore(coro):
    async with SEM:
        return await coro


async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            try:
                return await fut
            except Exception:
                return None
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await runner()
        if not fut.done():
            fut.set_result(result)
        return result
    except Exception:
        if not fut.done():
            fut.set_result(None)
        return None
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


async def race_ytdlp_and_api(yt_task, api_task, title: str):
    done, pending = await asyncio.wait(
        {yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in done:
        try:
            result = task.result()
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(title, source)
                for p in pending:
                    p.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await p
                return result
        except Exception:
            pass
    for task in pending:
        try:
            result = await task
            if result and os.path.exists(result):
                source = "yt-dlp" if task is yt_task else "API"
                log_download_source(title, source)
                return result
        except (asyncio.CancelledError, Exception):
            pass
    return None


async def _download_with_fallback(
    link: str,
    fmt: str,
    media_type: str,
    vid: str,
    title: str,
    api_coro,
) -> Optional[str]:
    loop = asyncio.get_running_loop()
    ytdlp_task = asyncio.create_task(
        run_with_semaphore(
            loop.run_in_executor(None, download_with_ytdlp_sync, link, fmt)
        )
    )
    api_task = asyncio.create_task(api_coro) if api_coro is not None else None
    if api_task:
        result = await race_ytdlp_and_api(ytdlp_task, api_task, title or "Unknown")
    else:
        result = await ytdlp_task
        if result and title:
            log_download_source(title, "yt-dlp")

    if result:
        return result

    if vid and title:
        if media_type == "audio":
            fb = await _fallback_download_audio(vid, title)
            if fb:
                fb_path, fb_source = fb
                log_download_source(title, fb_source)
                return fb_path
        elif media_type == "video":
            queries = _build_search_queries(title)
            if queries:
                dm_path = await run_with_semaphore(
                    loop.run_in_executor(None, _dailymotion_video_fallback_sync, vid, queries, title)
                )
                if dm_path:
                    log_download_source(title, "Dailymotion-Search")
                    return dm_path
    return None


async def yt_dlp_download(link: str, type: str, title: str = "") -> Optional[str]:
    vid = extract_video_id(link)
    if cached := find_cached_file(vid, media_type=type):
        if title:
            LOGGER.info(f"Track '{title}' - Served from cache")
        return cached

    if type == "audio":
        return await deduplicate_download(
            f"audio:{link}",
            lambda: _download_with_fallback(
                link,
                "bestaudio[ext=webm][acodec=opus]/bestaudio/best",
                "audio",
                vid,
                title,
                api_download_audio(link) if USE_AUDIO_API else None,
            ),
        )

    if type == "video":
        return await deduplicate_download(
            f"video:{link}",
            lambda: _download_with_fallback(
                link,
                "(bestvideo[height<=?720][width<=?1280][ext=mp4]/bestvideo[height<=?720])+(bestaudio[ext=m4a]/bestaudio)/best[height<=?720]/best",
                "video",
                vid,
                title,
                api_download_video(link) if USE_VIDEO_API else None,
            ),
        )

    return None
