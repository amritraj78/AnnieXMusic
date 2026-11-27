# Authored By Certified Coders © 2025
import asyncio
import contextlib
import glob
import html
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import aiofiles
import aiohttp
from yt_dlp import YoutubeDL

from AnnieXMedia.core.dir import CACHE_DIR, DOWNLOAD_DIR
from AnnieXMedia.core.http_pool import close_http_session, get_http_session
from AnnieXMedia.core.security import is_safe_http_url, sanitize_ext, sanitize_id_token
from AnnieXMedia.utils.cookie_handler import get_valid_cookie_file
from AnnieXMedia.utils.tuning import CHUNK_SIZE, SEM
from config import API_KEY, API_URL, VIDEO_API_URL
from AnnieXMedia.logging import LOGGER

LOGGER = LOGGER(__name__)

USE_AUDIO_API = bool(API_URL and API_KEY)
USE_VIDEO_API = bool(VIDEO_API_URL and API_KEY)
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
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
    if not re.match(r"^https?://(?:[\w-]+\.)?(?:youtube\.com|youtu\.be)/", low):
        return ""
    if "v=" in s:
        cand = s.split("v=", 1)[1].split("&", 1)[0].split("#", 1)[0]
        return cand if YOUTUBE_ID_RE.match(cand) else ""
    last = s.split("/")[-1].split("?", 1)[0].split("#", 1)[0]
    return last if YOUTUBE_ID_RE.match(last) else ""


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


async def download_file(url: str, out_path: str) -> Optional[str]:
    if not url or not await is_safe_http_url(url):
        return None
    os.makedirs(os.path.dirname(out_path) or DOWNLOAD_DIR, exist_ok=True)
    part_path = f"{out_path}.part"
    try:
        session = await get_http_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                return None
            total = 0
            async with aiofiles.open(part_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 512 * 1024 * 1024:
                        raise ValueError("Remote media exceeded 512MB limit")
                    await f.write(chunk)
        if total < 4096:
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
            async with session.get(poll_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
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
                fmt = sanitize_ext(
                    f"x.{data.get('format', 'webm')}",
                    allowed=("mp3", "m4a", "webm", "ogg", "opus", "mp4"),
                    default="webm",
                )
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
            async with session.get(poll_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
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
                fmt = sanitize_ext(
                    f"x.{data.get('format', 'mp4')}",
                    allowed=("mp4", "mkv", "webm"),
                    default="mp4",
                )
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
    r"\b(official(\s+music)?(\s+video)?|lyrical|lyric\s*video|lyrics|full\s*(video\s+)?(song|video|audio)|music\s*video|video\s*song|audio\s*song|song\s+with\s+lyrics|4k|uhd|full\s*hd|t-series|zee\s*music(\s*company)?|yrf|sony\s*music(\s*india)?|tips\s*official|speed\s*records|vevo)\b",
    re.I,
)
_VARIANT_TOKENS = {
    "cover", "karaoke", "instrumental", "remix", "lofi", "lo-fi",
    "slowed", "reverb", "nightcore", "8d", "mashup", "sped",
    "ringtone", "reaction", "teaser", "trailer", "tutorial", "dj",
}
_AUDIUS_API = "https://api.audius.co"
_JIOSAAVN_SUMIT_API = "https://saavn.sumit.co"
_JIOSAAVN_OFFICIAL_API = "https://www.jiosaavn.com/api.php"
_JIOSAAVN_HEADERS = {
    "Referer": "https://www.jiosaavn.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


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
    if parts:
        p0_clean = " ".join(parts[0].split()[:7])
        candidates.append(p0_clean)
        if " - " in parts[0]:
            left, right = [s.strip() for s in parts[0].split(" - ", 1)]
            if left:
                candidates.append(left)
            if right:
                candidates.append(right)
        if len(parts) >= 2:
            p0_words = parts[0].split()
            p1_words = parts[1].split()
            if len(p0_words) + len(p1_words) <= 8:
                candidates.append(f"{parts[0]} {parts[1]}")
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

    for q in queries[:3]:
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


async def _download_http_audio(
    vid: str,
    ext: str,
    stream_url: str,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    safe_vid = sanitize_id_token(vid)
    safe_ext = sanitize_ext(f"x.{ext}", allowed=("mp3", "m4a", "webm", "ogg", "opus", "mp4"), default="mp3")
    if not stream_url or not safe_vid or not await is_safe_http_url(stream_url):
        return None
    await asyncio.to_thread(os.makedirs, DOWNLOAD_DIR, exist_ok=True)
    out_path = f"{DOWNLOAD_DIR}/{safe_vid}.{safe_ext}"
    part_path = f"{out_path}.part"

    try:
        session = await get_http_session()
        async with session.get(
            stream_url,
            headers=headers,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            if resp.status not in (200, 206):
                return None
            total = 0
            async with aiofiles.open(part_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 256 * 1024 * 1024:
                        raise ValueError("Remote audio exceeded 256MB safety limit")
                    await f.write(chunk)
        if total < 16384:
            await asyncio.to_thread(lambda: os.remove(part_path) if os.path.exists(part_path) else None)
            return None
        await asyncio.to_thread(os.replace, part_path, out_path)
        return out_path if os.path.exists(out_path) else None
    except Exception:
        await asyncio.to_thread(lambda: os.remove(part_path) if os.path.exists(part_path) else None)
        return None


async def _download_audius_track(vid: str, track: Dict) -> Optional[str]:
    tid = track.get("id")
    if not tid:
        return None
    stream_url = f"{_AUDIUS_API}/v1/tracks/{tid}/stream?app_name=AnnieXMusic"
    return await _download_http_audio(vid, "mp3", stream_url)


async def _resolve_jiosaavn_official_url(
    session: aiohttp.ClientSession, song_id: str
) -> Optional[str]:
    try:
        async with session.get(
            _JIOSAAVN_OFFICIAL_API,
            params={
                "__call": "song.getDetails",
                "cc": "in",
                "_marker": "0",
                "_format": "json",
                "pids": song_id,
            },
            headers=_JIOSAAVN_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json(content_type=None)
    except Exception:
        return None

    song_obj = payload.get(song_id) if isinstance(payload, dict) else None
    if not isinstance(song_obj, dict):
        songs = payload.get("songs") if isinstance(payload, dict) else None
        song_obj = songs[0] if isinstance(songs, list) and songs else None
    if not isinstance(song_obj, dict):
        return None

    enc_url = song_obj.get("encrypted_media_url")
    if not enc_url:
        return None
    bitrate = "320" if str(song_obj.get("320kbps", "")).lower() == "true" else "160"

    try:
        async with session.get(
            _JIOSAAVN_OFFICIAL_API,
            params={
                "__call": "song.generateAuthToken",
                "url": enc_url,
                "bitrate": bitrate,
                "api_version": "4",
                "_format": "json",
                "ctx": "web6dot0",
                "_marker": "0",
            },
            headers=_JIOSAAVN_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                return None
            tok_data = await resp.json(content_type=None)
    except Exception:
        return None

    auth_url = tok_data.get("auth_url") if isinstance(tok_data, dict) else None
    return str(auth_url) if auth_url and str(auth_url).startswith("http") else None


async def _search_jiosaavn_best(
    queries: List[str], raw_title: str
) -> Optional[Tuple[float, Dict]]:
    session = await get_http_session()
    best: Optional[Tuple[float, Dict]] = None

    # 1. Fast direct search via saavn.sumit.co (includes CDN downloadUrl array)
    for q in queries[:3]:
        try:
            async with session.get(
                f"{_JIOSAAVN_SUMIT_API}/api/search/songs",
                params={"query": q, "limit": "6"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    continue
                payload = await resp.json(content_type=None)
        except Exception:
            continue

        songs = ((payload.get("data") or {}).get("results") if isinstance(payload, dict) else None)
        if not isinstance(songs, list):
            continue

        for song in songs[:6]:
            if not isinstance(song, dict):
                continue
            dl_urls = song.get("downloadUrl") or []
            best_dl = dl_urls[-1].get("url") if isinstance(dl_urls, list) and dl_urls else None
            if not best_dl:
                continue
            try:
                dur = int(song.get("duration") or 0)
            except (ValueError, TypeError):
                dur = 0
            title = html.unescape(str(song.get("name") or ""))
            artists_obj = (song.get("artists") or {}).get("primary") or []
            artist = ", ".join(
                html.unescape(str(a.get("name") or ""))
                for a in artists_obj[:3]
                if isinstance(a, dict)
            )
            sc = _score_track_candidate(q, raw_title, title, dur, artist)
            if best is None or sc > best[0]:
                best = (sc, {"url": str(best_dl), "ext": "m4a", "headers": _JIOSAAVN_HEADERS, "source": "JioSaavn"})

        if best and best[0] >= 2.0:
            return best

    if best is not None:
        return best

    # 2. Backup: official www.jiosaavn.com search -> generateAuthToken for top match
    best_id: Optional[Tuple[float, str]] = None
    for q in queries[:2]:
        try:
            async with session.get(
                _JIOSAAVN_OFFICIAL_API,
                params={
                    "__call": "search.getResults",
                    "_format": "json",
                    "_marker": "0",
                    "cc": "in",
                    "q": q,
                },
                headers=_JIOSAAVN_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    continue
                payload = await resp.json(content_type=None)
        except Exception:
            continue

        songs = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(songs, list):
            continue
        for song in songs[:6]:
            if not isinstance(song, dict) or not song.get("id"):
                continue
            title = html.unescape(str(song.get("song") or song.get("title") or ""))
            artist = html.unescape(str(song.get("primary_artists") or song.get("singers") or ""))
            # search.getResults omits duration on light results; use 180s neutral fallback so scorer stays fair
            sc = _score_track_candidate(q, raw_title, title, 180, artist)
            if best_id is None or sc > best_id[0]:
                best_id = (sc, str(song["id"]))
        if best_id and best_id[0] >= 2.0:
            break

    if best_id and best_id[0] >= 0.0:
        if auth_url := await _resolve_jiosaavn_official_url(session, best_id[1]):
            return best_id[0], {"url": auth_url, "ext": "m4a", "headers": _JIOSAAVN_HEADERS, "source": "JioSaavn-Official"}

    return None


async def _download_jiosaavn_track(vid: str, track: Dict) -> Optional[str]:
    return await _download_http_audio(
        vid,
        str(track.get("ext") or "m4a"),
        str(track.get("url") or ""),
        headers=track.get("headers"),
    )


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


def _dailymotion_fallback_sync(
    vid: str, queries: List[str], raw_title: str, media_type: str = "video"
) -> Optional[str]:
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
    dl_opts["format"] = (
        "bestaudio/best"
        if media_type == "audio"
        else "best[height<=?720][width<=?1280]/bestvideo[height<=?720]+bestaudio/best"
    )
    try:
        with YoutubeDL(dl_opts) as ydl:
            info = ydl.extract_info(best[1], download=True)
            return get_final_path_from_info(info, vid_override=vid)
    except Exception as e:
        LOGGER.warning(f"Dailymotion {media_type} fallback error for {vid}: {e}")
        return None


async def _fallback_download_audio(vid: str, title: str) -> Optional[Tuple[str, str]]:
    queries = _build_search_queries(title)
    if not queries or not vid:
        return None

    # Search JioSaavn and Audius concurrently for lowest latency
    jio_res, aud_res = await asyncio.gather(
        _search_jiosaavn_best(queries, title),
        _search_audius_best(queries, title),
        return_exceptions=True,
    )
    jio_best = jio_res if isinstance(jio_res, tuple) else None
    audius_best = aud_res if isinstance(aud_res, tuple) else None

    # Rank strong candidates (prefer JioSaavn slightly when tied due to 320kbps AAC quality)
    ranked: List[Tuple[float, float, str, Dict]] = []
    if jio_best:
        ranked.append((jio_best[0] + 0.35, jio_best[0], str(jio_best[1].get("source") or "JioSaavn"), jio_best[1]))
    if audius_best:
        ranked.append((audius_best[0], audius_best[0], "Audius", audius_best[1]))
    ranked.sort(key=lambda item: item[0], reverse=True)

    for _, raw_score, source_label, cand in ranked:
        if raw_score < 1.8:
            continue
        downloader = _download_jiosaavn_track if source_label.startswith("JioSaavn") else _download_audius_track
        if path := await downloader(vid, cand):
            return path, source_label

    loop = asyncio.get_running_loop()
    sc_path = await run_sync_with_semaphore(_soundcloud_fallback_sync, vid, queries, title)
    if sc_path:
        return sc_path, "SoundCloud-Search"

    for _, raw_score, source_label, cand in ranked:
        if 0.0 <= raw_score < 1.8:
            downloader = _download_jiosaavn_track if source_label.startswith("JioSaavn") else _download_audius_track
            if path := await downloader(vid, cand):
                return path, source_label

    dm_path = await run_sync_with_semaphore(_dailymotion_fallback_sync, vid, queries, title, "audio")
    if dm_path:
        return dm_path, "Dailymotion-Audio"

    return None


def download_with_ytdlp_sync(link: str, fmt: str) -> Optional[str]:
    base_opts = get_ytdlp_base_opts()
    has_cookies = "cookiefile" in base_opts
    client_profiles = [None, ["web", "tv"]] if has_cookies else [None, ["android_vr"]]

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
            err_low = str(e).lower()
            if not has_cookies and ("sign in" in err_low or "not a bot" in err_low or "cookies" in err_low):
                break

    LOGGER.warning(
        f"yt-dlp download error for {link}: {last_err or 'no downloadable format found'}"
    )
    return None


async def run_with_semaphore(coro):
    async with SEM:
        return await coro


async def run_sync_with_semaphore(func, *args):
    async with SEM:
        return await asyncio.to_thread(func, *args)


async def deduplicate_download(key: str, runner):
    async with _inflight_lock:
        if fut := _inflight.get(key):
            try:
                return await fut
            except BaseException:
                return None
        fut = asyncio.get_running_loop().create_future()
        _inflight[key] = fut
    try:
        result = await runner()
        if not fut.done():
            fut.set_result(result)
        return result
    except BaseException:
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
    ytdlp_task = asyncio.create_task(
        run_sync_with_semaphore(download_with_ytdlp_sync, link, fmt)
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
                dm_path = await run_sync_with_semaphore(_dailymotion_fallback_sync, vid, queries, title, "video")
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
