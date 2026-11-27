# Authored By Certified Coders © 2025
import asyncio
import os

from config import autoclean


def _remove_if_file(path: str) -> None:
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


async def _clean_entry(entry: dict):
    rem = entry.get("file") if isinstance(entry, dict) else None
    if not rem:
        return
    if rem in autoclean:
        autoclean.remove(rem)
    count = autoclean.count(rem)
    if count == 0:
        if not any(k in str(rem) for k in ("vid_", "live_", "index_")):
            await asyncio.to_thread(_remove_if_file, rem)


async def auto_clean(popped):
    if not popped:
        return
    try:
        if isinstance(popped, list):
            for entry in popped:
                await _clean_entry(entry)
        elif isinstance(popped, dict):
            await _clean_entry(popped)
    except Exception:
        pass
