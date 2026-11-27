# Authored By Certified Coders © 2025
import asyncio
import re
from typing import Any, Dict, Optional, Tuple

from yt_dlp import YoutubeDL

from AnnieXMedia.utils.downloader import yt_dlp_download
from AnnieXMedia.utils.formatters import seconds_to_min
from AnnieXMedia.core.security import is_safe_http_url

_SC_RE = re.compile(r"^https?://(soundcloud\.com|on\.soundcloud\.com)/.+", re.I)


class SoundAPI:
    async def valid(self, link: Optional[str]) -> bool:
        return bool(link and _SC_RE.match(link))

    async def _extract_info(self, url: str) -> Dict[str, Any]:
        if not await self.valid(url) or not await is_safe_http_url(url):
            return {}

        def _run(u: str):
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "skip_download": True,
                "socket_timeout": 12,
            }
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(u, download=False)

        info = await asyncio.wait_for(asyncio.to_thread(_run, url), timeout=20.0)
        if not info:
            return {}

        _type = str(info.get("_type", ""))
        if _type in ("url", "url_transparent") and info.get("url"):
            redir = str(info["url"])
            if await is_safe_http_url(redir):
                sub_info = await asyncio.wait_for(asyncio.to_thread(_run, redir), timeout=20.0)
                if sub_info:
                    info = sub_info

        return info or {}

    async def download(self, url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            info = await self._extract_info(url)
        except Exception:
            return None, None

        if not info or info.get("_type") == "playlist":
            return None, None

        title = (info.get("title") or "SoundCloud").strip()
        try:
            duration_sec = int(info.get("duration") or 0)
        except Exception:
            duration_sec = 0

        uploader = info.get("uploader") or ""
        thumb = (
            info.get("thumbnail")
            or (info.get("thumbnails") or [{}])[0].get("url")
            or ""
        )

        out_path: Optional[str] = await yt_dlp_download(url, type="audio", title=title)
        if not out_path:
            return None, None

        details = {
            "title": title,
            "duration_sec": duration_sec,
            "duration_min": seconds_to_min(max(duration_sec, 0)),
            "uploader": uploader,
            "thumb": thumb,
            "filepath": out_path,
        }
        return details, out_path
