# Authored By Certified Coders © 2025
import asyncio
import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.aio import VideosSearch
from config import YOUTUBE_IMG_URL
from AnnieXMedia.core.dir import CACHE_DIR
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.core.security import is_safe_http_url, safe_path_under, sanitize_id_token


PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 170
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580

def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


def _process_image(thumb_path: str, cache_path: str, title: str, views: str, is_live: bool, duration_text: str):
    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    # Frosted glass panel
    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    # Draw details
    draw = ImageDraw.Draw(bg)
    try:
        title_font = ImageFont.truetype("AnnieXMedia/assets/thumb/font2.ttf", 32)
        regular_font = ImageFont.truetype("AnnieXMedia/assets/thumb/font.ttf", 18)
    except OSError:
        title_font = regular_font = ImageFont.load_default()

    thumb = base.resize((THUMB_W, THUMB_H))
    tmask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    # Progress bar
    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    end_text = "Live" if is_live else duration_text
    draw.text((BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60), BAR_Y + 15), end_text, fill="red" if is_live else "black", font=regular_font)

    # Icons
    icons_path = "AnnieXMedia/assets/thumb/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        r, g, b, a = ic.split()
        black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
        bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

    bg.save(cache_path)


async def get_thumb(videoid: str) -> str:
    safe_vid = sanitize_id_token(videoid, "track")
    cache_p = safe_path_under(CACHE_DIR, f"{safe_vid}_v4.png")
    thumb_p = safe_path_under(CACHE_DIR, f"thumb_{safe_vid}.png")
    if cache_p is None or thumb_p is None:
        return YOUTUBE_IMG_URL
    cache_path, thumb_path = str(cache_p), str(thumb_p)

    if os.path.exists(cache_path):
        return cache_path

    # YouTube video data fetch
    results = VideosSearch(f"https://www.youtube.com/watch?v={safe_vid}", limit=1)
    try:
        results_data = await results.next()
        result_items = results_data.get("result", [])
        if not result_items:
            raise ValueError("No results found.")
        data = result_items[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    if not await is_safe_http_url(thumbnail):
        thumbnail = YOUTUBE_IMG_URL

    try:
        session = await get_http_session()
        async with session.get(thumbnail, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                total = 0
                chunks = []
                async for chunk in resp.content.iter_chunked(65536):
                    total += len(chunk)
                    if total > 10 * 1024 * 1024:
                        return YOUTUBE_IMG_URL
                    chunks.append(chunk)
                async with aiofiles.open(thumb_path, "wb") as f:
                    await f.write(b"".join(chunks))
            else:
                return YOUTUBE_IMG_URL
    except Exception:
        return YOUTUBE_IMG_URL

    if not os.path.exists(thumb_path):
        return YOUTUBE_IMG_URL

    try:
        await asyncio.to_thread(_process_image, thumb_path, cache_path, title, views, is_live, duration_text)
    except Exception:
        return YOUTUBE_IMG_URL
    finally:
        def _rm_thumb():
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except OSError:
                pass
        await asyncio.to_thread(_rm_thumb)

    return cache_path if os.path.exists(cache_path) else YOUTUBE_IMG_URL
