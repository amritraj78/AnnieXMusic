# Authored By Certified Coders © 2025
import asyncio
import re
from typing import List, Optional, Tuple, Union

from bs4 import BeautifulSoup
from youtubesearchpython.aio import VideosSearch

from AnnieXMedia.core.security import fetch_url_limited


class AppleAPI:
    def __init__(self):
        self.regex = r"^https?://music\.apple\.com/.+"
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str) -> bool:
        return bool(link and re.search(self.regex, link))

    async def track(self, url: str, playid: Union[bool, str] = None) -> Tuple[Optional[dict], Optional[str]]:
        if not url:
            return None, None
        target = self.base + url if playid else url
        if not await self.valid(target):
            return None, None

        ok, status, _, body = await fetch_url_limited(target, max_bytes=3 * 1024 * 1024, timeout=15.0)
        if not ok or status != 200 or not body:
            return None, None

        html_text = body.decode("utf-8", errors="replace")

        def _parse_title(raw_html: str) -> Optional[str]:
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup.find_all("meta"):
                if tag.get("property") == "og:title":
                    return tag.get("content")
            return None

        title_query = await asyncio.to_thread(_parse_title, html_text)
        if not title_query:
            return None, None

        try:
            data = await VideosSearch(title_query, limit=1).next()
        except Exception:
            return None, None
        items = data.get("result") or []
        if not items:
            return None, None

        r = items[0]
        thumbs = r.get("thumbnails") or []
        thumb_url = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
        track_details = {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "vidid": r.get("id", ""),
            "duration_min": r.get("duration"),
            "thumb": thumb_url,
        }
        return track_details, track_details["vidid"]

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Tuple[Optional[List[str]], Optional[str]]:
        if not url:
            return None, None
        target = self.base + url if playid else url
        if not await self.valid(target) or "playlist/" not in target:
            return None, None

        try:
            playlist_id = target.split("playlist/", 1)[1].split("?", 1)[0]
        except Exception:
            return None, None

        ok, status, _, body = await fetch_url_limited(target, max_bytes=3 * 1024 * 1024, timeout=15.0)
        if not ok or status != 200 or not body:
            return None, None

        html_text = body.decode("utf-8", errors="replace")

        def _parse_songs(raw_html: str) -> List[str]:
            soup = BeautifulSoup(raw_html, "html.parser")
            applelinks = soup.find_all("meta", attrs={"property": "music:song"})
            out: List[str] = []
            for item in applelinks:
                content = str(item.get("content") or "")
                if "album/" in content:
                    slug = content.split("album/", 1)[1].split("/", 1)[0]
                    if slug:
                        out.append(slug.replace("-", " "))
            return out

        results = await asyncio.to_thread(_parse_songs, html_text)
        return (results, playlist_id) if results else (None, None)
