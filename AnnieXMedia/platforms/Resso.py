# Authored By Certified Coders © 2025
import asyncio
import re
from typing import Optional, Tuple, Union

from bs4 import BeautifulSoup
from youtubesearchpython.aio import VideosSearch

from AnnieXMedia.utils.security import fetch_url_limited


class RessoAPI:
    def __init__(self):
        self.regex = r"^https?://(?:www\.)?m\.resso\.com/.+"
        self.base = "https://m.resso.com/"

    async def valid(self, link: Optional[str]) -> bool:
        return bool(link and re.search(self.regex, link))

    async def track(self, url: Optional[str], playid: Union[bool, str] = None) -> Tuple[Optional[dict], Optional[str]]:
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

        title = await asyncio.to_thread(_parse_title, html_text)
        if not title:
            return None, None

        try:
            data = await VideosSearch(title, limit=1).next()
        except Exception:
            return None, None
        search_res = data.get("result") or []
        if not search_res:
            return None, None

        result = search_res[0]
        thumbs = result.get("thumbnails") or []
        thumb_url = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
        track_details = {
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "vidid": result.get("id", ""),
            "duration_min": result.get("duration"),
            "thumb": thumb_url,
        }
        return track_details, track_details["vidid"]
