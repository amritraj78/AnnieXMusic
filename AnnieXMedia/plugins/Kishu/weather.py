# Authored By Certified Coders © 2025
import html
import os
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.downloader import get_http_session

weather_apikey = os.getenv("WEATHER_API_KEY", "8de2d8b3a93542c9a2d8b3a935a2c909")
get_coords_url = "https://api.weather.com/v3/location/search"
weather_data_url = "https://api.weather.com/v3/aggcommon/v3-wx-observations-current"

headers = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; M2012K11AG Build/SQ1D.211205.017)"
}


@app.on_message(filters.command("weather"))
async def weather_command(client: Client, message: Message):
    if len(message.command) == 1:
        return await message.reply_text(
            "<b>ᴜsᴀɢᴇ:</b> <code>/weather city</code>\nExample: <code>/weather delhi</code>",
            parse_mode=enums.ParseMode.HTML
        )

    parts = (message.text or message.caption or "").split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ""
    if not query or len(query) > 120:
        return await message.reply_text(
            "❌ <b>Please enter a valid city name.</b>",
            parse_mode=enums.ParseMode.HTML
        )

    try:
        http = await get_http_session()
        async with http.get(
            get_coords_url,
            headers=headers,
            params={
                "apiKey": weather_apikey,
                "format": "json",
                "language": "en",
                "query": query
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as coord_response:
            if coord_response.status != 200:
                return await message.reply_text(
                    "❌ <b>Location not found.</b> Please try a different city.",
                    parse_mode=enums.ParseMode.HTML
                )
            try:
                coord_data = await coord_response.json()
            except Exception:
                coord_data = {}

        lat_list = coord_data.get("location", {}).get("latitude", [])
        lon_list = coord_data.get("location", {}).get("longitude", [])
        addr_list = coord_data.get("location", {}).get("address", [])
        if not lat_list or not lon_list or not addr_list:
            return await message.reply_text(
                "❌ <b>Location not found.</b> Please try a different city.",
                parse_mode=enums.ParseMode.HTML
            )

        latitude = lat_list[0]
        longitude = lon_list[0]
        location_name = html.escape(str(addr_list[0]))

        async with http.get(
            weather_data_url,
            headers=headers,
            params={
                "apiKey": weather_apikey,
                "format": "json",
                "language": "en",
                "geocode": f"{latitude},{longitude}",
                "units": "m"
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as weather_response:
            if weather_response.status != 200:
                return await message.reply_text(
                    "⚠️ <b>Weather data not available</b> at the moment.",
                    parse_mode=enums.ParseMode.HTML
                )
            try:
                weather_data = await weather_response.json()
            except Exception:
                weather_data = {}
        obs = weather_data.get("v3-wx-observations-current", {})

        if not obs:
            return await message.reply_text(
                "⚠️ <b>Weather data not available</b> at the moment.",
                parse_mode=enums.ParseMode.HTML
            )

        weather_text = (
            f"<b>{location_name}</b> 🌍\n\n"
            f"🌡️ <b>ᴛᴇᴍᴘᴇʀᴀᴛᴜʀᴇ:</b> <code>{html.escape(str(obs.get('temperature', 'N/A')))} °C</code>\n"
            f"🥵 <b>ғᴇᴇʟs ʟɪᴋᴇ:</b> <code>{html.escape(str(obs.get('temperatureFeelsLike', 'N/A')))} °C</code>\n"
            f"💧 <b>ʜᴜᴍɪᴅɪᴛʏ:</b> <code>{html.escape(str(obs.get('relativeHumidity', 'N/A')))}%</code>\n"
            f"💨 <b>ᴡɪɴᴅ:</b> <code>{html.escape(str(obs.get('windSpeed', 'N/A')))} km/h</code>\n"
            f"☁️ <b>ᴄᴏɴᴅɪᴛɪᴏɴ:</b> <i>{html.escape(str(obs.get('wxPhraseLong', 'N/A')))}</i>"
        )

        await message.reply_text(weather_text, parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        LOGGER(__name__).warning(f"Error in /weather: {e}")
        await message.reply_text(
            "❌ <b>An error occurred</b> while fetching the weather. Please try again later.",
            parse_mode=enums.ParseMode.HTML
        )
