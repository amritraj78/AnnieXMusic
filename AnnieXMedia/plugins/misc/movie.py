# Authored By Certified Coders © 2025
import asyncio
import html
import os
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.downloader import get_http_session


TMDB_API_KEY = os.getenv("TMDB_API_KEY", "23c3b139c6d59ebb608fe6d5b974d888")
TMDB_BASE = "https://api.themoviedb.org/3"


@app.on_message(filters.command("movie"))
async def movie_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide a movie name.\n\nExample: `/movie Inception`",
            parse_mode=ParseMode.MARKDOWN
        )

    movie_name = " ".join(message.command[1:])
    status = await message.reply_text("🔎 Searching for the movie...")

    try:
        info = await get_movie_info(movie_name)
        await status.edit_text(info, parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER(__name__).warning(f"[Movie Error] {e}")
        await status.edit_text("❌ Failed to fetch movie information.")


async def get_movie_info(query: str) -> str:
    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=10)

    async with session.get(
        f"{TMDB_BASE}/search/movie",
        params={"api_key": TMDB_API_KEY, "query": query},
        timeout=timeout,
    ) as search:
        if search.status != 200:
            return "❌ Movie service unavailable. Try again later."
        try:
            search_data = await search.json()
        except Exception:
            return "❌ Failed to parse movie response."

    results = search_data.get("results") or []
    if not results:
        return "❌ Movie not found."

    movie = results[0]
    movie_id = movie.get("id")
    if not movie_id:
        return "❌ Movie not found."

    async def _get_json(url: str) -> dict:
        try:
            async with session.get(url, params={"api_key": TMDB_API_KEY}, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return {}

    details_data, cast_data = await asyncio.gather(
        _get_json(f"{TMDB_BASE}/movie/{movie_id}"),
        _get_json(f"{TMDB_BASE}/movie/{movie_id}/credits"),
    )

    actors = ", ".join(
        html.escape(str(actor.get("name", "")))
        for actor in (cast_data.get("cast") or [])[:5]
        if isinstance(actor, dict) and actor.get("name")
    ) or "N/A"

    title = html.escape(str(details_data.get("title") or movie.get("title") or "N/A"))
    release = html.escape(str(details_data.get("release_date") or "N/A"))
    overview = html.escape(str(details_data.get("overview") or "N/A"))
    rating = html.escape(str(details_data.get("vote_average") or "N/A"))
    revenue = details_data.get("revenue", 0)

    revenue_str = f"${revenue:,}" if isinstance(revenue, (int, float)) and revenue > 0 else "Not Available"

    info = (
        f"🎬 <b>Title:</b> {title}\n"
        f"📅 <b>Release Date:</b> {release}\n"
        f"⭐ <b>Rating:</b> {rating}/10\n"
        f"🎭 <b>Top Cast:</b> {actors}\n"
        f"💰 <b>Box Office:</b> {revenue_str}\n\n"
        f"📝 <b>Overview:</b>\n{overview[:2500]}"
    )

    return info[:4000]
