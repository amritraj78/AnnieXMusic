# Authored By Certified Coders © 2025
import aiohttp


import socket
from asyncio import get_running_loop
from functools import partial


def _netcat(host, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10.0)
    try:
        s.connect((host, port))
        s.sendall(content.encode())
        s.shutdown(socket.SHUT_WR)
        data = s.recv(4096).decode("utf-8").strip("\n\x00")
        return data if data else None
    except Exception:
        return None
    finally:
        s.close()


async def paste(content):
    loop = get_running_loop()
    link = await loop.run_in_executor(None, partial(_netcat, "ezup.dev", 9999, content))
    return link


####2nd paste code 

BASE = "https://batbin.me/"


async def post(url: str, *args, **kwargs):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(url, *args, **kwargs) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = await resp.text()
                return data
    except Exception:
        return None


async def ANNIEBIN(text):
    if not text:
        return None
    text_str = str(text)
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
