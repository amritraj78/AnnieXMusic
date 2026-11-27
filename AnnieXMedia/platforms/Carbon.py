# Authored By Certified Coders © 2025
import asyncio
import random
import time
from pathlib import Path

import aiohttp
from aiohttp import client_exceptions

from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.core.security import safe_path_under, sanitize_id_token


class UnableToFetchCarbon(Exception):
    pass


themes = [
    "3024-night", "a11y-dark", "blackboard", "base16-dark", "base16-light",
    "cobalt", "duotone-dark", "dracula-pro", "hopscotch", "lucario",
    "material", "monokai", "nightowl", "nord", "oceanic-next", "one-light",
    "one-dark", "panda-syntax", "parasio-dark", "seti", "shades-of-purple",
    "solarized+dark", "solarized+light", "synthwave-84", "twilight",
    "verminal", "vscode", "yeti", "zenburn",
]

colour = [
    "#FF0000", "#FF5733", "#FFFF00", "#008000", "#0000FF", "#800080", "#A52A2A",
    "#FF00FF", "#D2B48C", "#00FFFF", "#808000", "#800000", "#30D5C8", "#00FF00",
    "#008080", "#4B0082", "#EE82EE", "#FFC0CB", "#000000", "#FFFFFF", "#808080",
]

_MAX_IMAGE_BYTES = 10 * 1024 * 1024


class CarbonAPI:
    def __init__(self, cache_dir: str = "cache", timeout_s: int = 20):
        self.language = "auto"
        self.drop_shadow = True
        self.drop_shadow_blur = "68px"
        self.drop_shadow_offset = "20px"
        self.font_family = "JetBrains Mono"
        self.width_adjustment = True
        self.watermark = False

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = aiohttp.ClientTimeout(total=timeout_s)

    async def close(self):
        # Shared session is managed by downloader.close_http_session()
        return

    async def generate(self, text: str, user_id) -> str:
        if not text:
            raise UnableToFetchCarbon("Empty text.")
        if len(text) > 10000:
            raise UnableToFetchCarbon("Text too long (max 10k characters).")

        params = {
            "code": text,
            "backgroundColor": random.choice(colour),
            "theme": random.choice(themes),
            "dropShadow": self.drop_shadow,
            "dropShadowOffsetY": self.drop_shadow_offset,
            "dropShadowBlurRadius": self.drop_shadow_blur,
            "fontFamily": self.font_family,
            "language": self.language,
            "watermark": self.watermark,
            "widthAdjustment": self.width_adjustment,
        }

        url = "https://carbonara.solopov.dev/api/cook"
        session = await get_http_session()
        safe_uid = sanitize_id_token(str(user_id), "user")
        out = safe_path_under(self.cache_dir, f"carbon_{safe_uid}_{int(time.time() * 1000)}.jpg")
        if out is None:
            raise UnableToFetchCarbon("Invalid cache destination.")

        last_exc = None
        for _ in range(2):
            try:
                async with session.post(
                    url,
                    json=params,
                    timeout=self._timeout,
                    headers={"Content-Type": "application/json", "User-Agent": "AnnieXMusic/CarbonClient"},
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise UnableToFetchCarbon(f"Carbon API error {resp.status}: {body[:200]}")
                    chunks = []
                    total = 0
                    async for chunk in resp.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > _MAX_IMAGE_BYTES:
                            raise UnableToFetchCarbon("Carbon image exceeded safety size limit.")
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    await asyncio.to_thread(out.write_bytes, data)
                    return str(out)
            except (client_exceptions.ClientError, asyncio.TimeoutError, OSError) as e:
                last_exc = e
        raise UnableToFetchCarbon(f"Network error: {last_exc!r}")
