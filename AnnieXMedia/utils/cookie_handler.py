# Authored By Certified Coders © 2025
import asyncio
import os
import httpx
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from config import COOKIE_URL
from AnnieXMedia.utils.errors import capture_internal_err

COOKIE_PATH = Path("AnnieXMedia/assets/cookies.txt")
_NETSCAPE_HEADERS = ("# Netscape", "# HTTP Cookie File")


def is_valid_cookie_file(path: Path = COOKIE_PATH) -> bool:
    """Return True only if path exists, exceeds minimum size, and looks like Netscape cookies."""
    try:
        if not path or not path.is_file() or path.stat().st_size <= 50:
            return False
        content = path.read_text(encoding="utf-8", errors="ignore").lstrip()
        if not content.startswith(_NETSCAPE_HEADERS):
            return False
        return any(
            line.strip() and not line.lstrip().startswith("#")
            for line in content.splitlines()
        )
    except OSError:
        return False


def get_valid_cookie_file() -> Optional[str]:
    """Return string cookie path when valid, else None so yt-dlp never loads empty/corrupt cookies."""
    return str(COOKIE_PATH) if is_valid_cookie_file(COOKIE_PATH) else None


def _extract_paste_id(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""


def resolve_raw_cookie_url(url: str) -> str:
    url = (url or "").strip()
    low = url.lower()

    if "pastebin.com/" in low and "/raw/" not in low:
        paste_id = _extract_paste_id(url)
        return f"https://pastebin.com/raw/{paste_id}" if paste_id else url

    if "batbin.me/" in low:
        if "/api/v2/paste/" in low:
            return url
        paste_id = _extract_paste_id(url)
        return f"https://batbin.me/api/v2/paste/{paste_id}" if paste_id else url

    return url


@capture_internal_err
async def fetch_and_store_cookies():
    if not COOKIE_URL:
        if is_valid_cookie_file(COOKIE_PATH):
            return
        raise EnvironmentError("⚠️ ᴄᴏᴏᴋɪᴇ_ᴜʀʟ ɴᴏᴛ sᴇᴛ ɪɴ ᴇɴᴠ.")

    raw_url = resolve_raw_cookie_url(COOKIE_URL)

    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "annie-cookie-fetcher/1.0"},
            follow_redirects=True,
        ) as client:
            response = await client.get(raw_url)
            response.raise_for_status()
    except Exception as e:
        raise ConnectionError(f"⚠️ ᴄᴀɴ'ᴛ ꜰᴇᴛᴄʜ ᴄᴏᴏᴋɪᴇs:\n{e}")

    cookies = (response.text or "").strip()

    # If the response was JSON (e.g. from batbin API), extract the content field
    try:
        data = response.json()
        if isinstance(data, dict):
            for key in ("content", "data", "paste", "text"):
                if key in data and isinstance(data[key], str):
                    cookies = data[key].strip()
                    break
    except Exception:
        pass

    if not cookies.lstrip().startswith(_NETSCAPE_HEADERS):
        raise ValueError("⚠️ ɪɴᴠᴀʟɪᴅ ᴄᴏᴏᴋɪᴇ ꜰᴏʀᴍᴀᴛ. ɴᴇᴇᴅs ɴᴇᴛsᴄᴀᴘᴇ ꜰᴏʀᴍᴀᴛ.")

    if len(cookies) < 100:
        raise ValueError("⚠️ ᴄᴏᴏᴋɪᴇ ᴄᴏɴᴛᴇɴᴛ ᴛᴏᴏ sʜᴏʀᴛ. ᴘᴏssɪʙʟʏ ɪɴᴠᴀʟɪᴅ.")

    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        COOKIE_PATH.write_text(cookies, encoding="utf-8")
    except Exception as e:
        raise IOError(f"⚠️ ғᴀɪʟᴇᴅ ᴛᴏ sᴀᴠᴇ ᴄᴏᴏᴋɪᴇs: {e}")
