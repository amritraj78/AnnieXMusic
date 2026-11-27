# Authored By Certified Coders © 2025
import asyncio
import socket
from functools import partial

import aiohttp

from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.core.security import redact_secrets


def _netcat(host, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10.0)
    try:
        s.connect((host, port))
        s.sendall(content.encode())
        s.shutdown(socket.SHUT_WR)
        data = s.recv(4096).decode("utf-8", errors="replace").strip("\n\x00")
        return data if data else None
    except Exception:
        return None
    finally:
        s.close()


async def paste(content):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_netcat, "ezup.dev", 9999, content))


BASE = "https://batbin.me/"


async def post(url: str, *args, **kwargs):
    try:
        session = await get_http_session()
        async with session.post(
            url, *args, timeout=aiohttp.ClientTimeout(total=15), **kwargs
        ) as resp:
            try:
                return await resp.json(content_type=None)
            except Exception:
                return await resp.text()
    except Exception:
        return None


async def ANNIEBIN(text):
    if not text:
        return None
    text_str = redact_secrets(str(text))
    resp = await post(f"{BASE}api/v2/paste", data=text_str)
    if isinstance(resp, dict) and resp.get("success") and "message" in resp:
        return BASE + resp["message"]
    try:
        fallback = await paste(text_str)
        if fallback:
            return fallback
    except Exception:
        pass
    return None
