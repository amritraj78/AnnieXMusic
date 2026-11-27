# Authored By Certified Coders © 2025
import os
import time
from ..logging import LOGGER

BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
COUPLE_DIR = os.path.join(BASE_DIR, "couples")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
BACKUP_DIR = os.path.join(BASE_DIR, "AnnieXMediaBackup")
PLAYBACK_DIR = os.path.join(BASE_DIR, "playback")


def prune_storage_cache(
    max_age_seconds: int = 10800,
    max_total_bytes: int = 450 * 1024 * 1024,
) -> int:
    """Remove old downloaded/cached media files and cap disk footprint on PaaS hosts."""
    now = time.time()
    removed = 0
    files = []

    folders = [DOWNLOAD_DIR, CACHE_DIR, COUPLE_DIR]
    if os.path.isdir(PLAYBACK_DIR):
        try:
            for sub in os.scandir(PLAYBACK_DIR):
                if sub.is_dir():
                    folders.append(sub.path)
        except OSError:
            pass

    for folder in folders:
        if not os.path.isdir(folder):
            continue
        age_limit = 172800 if folder == COUPLE_DIR else max_age_seconds
        try:
            for entry in os.scandir(folder):
                if not entry.is_file() or entry.name.endswith(".part"):
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                if now - st.st_mtime > age_limit:
                    try:
                        os.remove(entry.path)
                        removed += 1
                    except OSError:
                        pass
                else:
                    files.append((st.st_mtime, st.st_size, entry.path))
        except OSError:
            continue

    total_size = sum(item[1] for item in files)
    if total_size > max_total_bytes:
        # Never prune very recent files (< 5 min) even during busy bursts
        recent_cutoff = now - 300
        for mtime, size, path in sorted(files, key=lambda x: x[0]):
            if total_size <= max_total_bytes:
                break
            if mtime > recent_cutoff:
                continue
            try:
                os.remove(path)
                total_size -= size
                removed += 1
            except OSError:
                pass

    return removed


def StorageManager():

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(COUPLE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    LOGGER(__name__).info("Directories Updated.")
