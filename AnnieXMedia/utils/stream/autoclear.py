# Authored By Certified Coders © 2025
import os

from config import autoclean


async def _clean_entry(entry: dict):
    rem = entry.get("file") if isinstance(entry, dict) else None
    if not rem:
        return
    if rem in autoclean:
        autoclean.remove(rem)
    count = autoclean.count(rem)
    if count == 0:
        if not any(k in str(rem) for k in ("vid_", "live_", "index_")) and os.path.isfile(rem):
            try:
                os.remove(rem)
            except OSError:
                pass


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
