# Authored By Certified Coders © 2025
import html
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)
from youtubesearchpython.aio import VideosSearch

from AnnieXMedia.utils.inlinequery import answer
from config import BANNED_USERS
from AnnieXMedia import app


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    text = query.query.strip().lower()
    answers = []
    if text.strip() == "":
        try:
            await client.answer_inline_query(query.id, results=answer, cache_time=10)
        except:
            return
    else:
        try:
            a = VideosSearch(text, limit=20)
            data = await a.next()
            result = data.get("result", [])
        except Exception:
            result = []

        if not result:
            return

        for x in range(min(15, len(result))):
            item = result[x]
            title = (item.get("title") or "Unknown").title()
            duration = item.get("duration") or "Unknown"
            views = (item.get("viewCount") or {}).get("short", "Unknown")
            thumbs = item.get("thumbnails", [{}])
            thumbnail = thumbs[0].get("url", "").split("?")[0] if thumbs and thumbs[0].get("url") else "https://telegra.ph/file/58afe55fee5ae99d6901b.jpg"
            channel_info = item.get("channel", {})
            channellink = channel_info.get("link", "https://youtube.com")
            channel = channel_info.get("name", "YouTube")
            link = item.get("link", "https://youtube.com")
            published = item.get("publishedTime", "Unknown")
            description = f"{views} | {duration} ᴍɪɴᴜᴛᴇs | {channel}  | {published}"
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʏᴏᴜᴛᴜʙᴇ 🎄",
                            url=link,
                        )
                    ],
                ]
            )
            searched_text = f"""
❄ <b>ᴛɪᴛʟᴇ :</b> <a href="{html.escape(link)}">{html.escape(title)}</a>

⏳ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> {html.escape(str(duration))} ᴍɪɴᴜᴛᴇs
👀 <b>ᴠɪᴇᴡs :</b> <code>{html.escape(str(views))}</code>
🎥 <b>ᴄʜᴀɴɴᴇʟ :</b> <a href="{html.escape(channellink)}">{html.escape(channel)}</a>
⏰ <b>ᴘᴜʙʟɪsʜᴇᴅ ᴏɴ :</b> {html.escape(str(published))}


<u><b>➻ ɪɴʟɪɴᴇ sᴇᴀʀᴄʜ ᴍᴏᴅᴇ ʙʏ {html.escape(app.name or 'AnnieXMusic')}</b></u>"""
            answers.append(
                InlineQueryResultPhoto(
                    photo_url=thumbnail,
                    title=title,
                    thumb_url=thumbnail,
                    description=description,
                    caption=searched_text,
                    reply_markup=buttons,
                )
            )
        try:
            return await client.answer_inline_query(query.id, results=answers)
        except Exception:
            return
