# Authored By Certified Coders © 2025
import html
import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from AnnieXMedia import app
from AnnieXMedia.utils.downloader import get_http_session


async def get_anime_info(anime_name):
    url = 'https://graphql.anilist.co'
    query = '''
    query ($anime: String) {
      Media (search: $anime, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        description(asHtml: false)
        episodes
        status
        averageScore
        coverImage {
          large
        }
      }
    }
    '''
    variables = {"anime": anime_name}
    try:
        session = await get_http_session()
        async with session.post(
            url,
            json={'query': query, 'variables': variables},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status != 200:
                return None, f"❌ HTTP {response.status} from AniList."
            data = await response.json()

        if 'errors' in data:
            return None, f"❌ Error: {data['errors'][0].get('message', 'Unknown error')}"

        return (data.get('data') or {}).get('Media'), None
    except Exception as e:
        return None, f"❌ Error: {e}"


def clean_description(desc):
    if not desc:
        return "No description available."
    desc = re.sub(r"<br\s*/?>", "\n", desc)
    desc = re.sub(r"<[^>]+>", "", desc)
    desc = desc.strip()
    return desc[:750] + "..." if len(desc) > 750 else desc


@app.on_message(filters.command("anime"))
async def anime_info(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "❌ Please provide an anime name.\n\nExample: `/anime Naruto`",
            parse_mode=ParseMode.MARKDOWN
        )

    anime_name = " ".join(message.command[1:])
    result, error = await get_anime_info(anime_name)

    if not result:
        return await message.reply_text(
            error or "❌ Anime not found.",
        )

    title_obj = result.get('title') or {}
    title = html.escape(str(title_obj.get('romaji') or title_obj.get('english') or 'Unknown'))
    english = title_obj.get('english')
    native = html.escape(str(title_obj.get('native') or 'N/A'))
    episodes = html.escape(str(result.get('episodes') or 'N/A'))
    status = html.escape(str(result.get('status') or 'N/A'))
    score = html.escape(str(result.get('averageScore') or 'N/A'))
    desc = html.escape(clean_description(result.get('description')))
    image = (result.get('coverImage') or {}).get('large')

    english_line = f"<b>🇺🇸 Title (English):</b> {html.escape(str(english))}\n" if english else ""

    caption = (
        f"<b>🎌 Title (Romaji):</b> {title}\n"
        f"{english_line}"
        f"<b>🈶 Title (Native):</b> {native}\n"
        f"<b>📺 Episodes:</b> {episodes}\n"
        f"<b>📊 Score:</b> {score}/100\n"
        f"<b>📌 Status:</b> {status}\n\n"
        f"<b>📝 Description:</b>\n{desc}"
    )

    if image:
        try:
            await message.reply_photo(
                image,
                caption=caption[:1024],
                parse_mode=ParseMode.HTML
            )
            return
        except Exception:
            pass
    await message.reply_text(
        caption[:4096],
        parse_mode=ParseMode.HTML
    )
