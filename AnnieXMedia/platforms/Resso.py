# Authored By Certified Coders © 2025
import re
from typing import Union

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.aio import VideosSearch


class RessoAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/m.resso.com\/)(.*)$"
        self.base = "https://m.resso.com/"

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def track(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        title = None
        des = None
        for tag in soup.find_all("meta"):
            if tag.get("property", None) == "og:title":
                title = tag.get("content", None)
            if tag.get("property", None) == "og:description":
                des = tag.get("content", None)
                try:
                    des = des.split("·")[0]
                except:
                    pass
        if not title:
            return False
        results = VideosSearch(title, limit=1)
        data = await results.next()
        search_res = data.get("result", [])
        if not search_res:
            return False
        result = search_res[0]
        thumbs = result.get("thumbnails", [])
        thumb_url = thumbs[0].get("url", "").split("?")[0] if thumbs else ""
        track_details = {
            "title": result.get("title", ""),
            "link": result.get("link", ""),
            "vidid": result.get("id", ""),
            "duration_min": result.get("duration"),
            "thumb": thumb_url,
        }
        return track_details, track_details["vidid"]
