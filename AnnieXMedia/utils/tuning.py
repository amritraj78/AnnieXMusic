# Authored By Certified Coders © 2025
import asyncio
import os

CPU = os.cpu_count() or 1
MAX_CONCURRENT = min(12, max(2, CPU * 2))
CHUNK_SIZE = 128 * 1024
YTDLP_TIMEOUT = 30
YOUTUBE_META_TTL = 600
YOUTUBE_META_MAX = 512
SEM = asyncio.Semaphore(MAX_CONCURRENT)
