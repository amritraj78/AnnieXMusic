# Authored By Certified Coders © 2025
import httpx
from pyrogram import Client, filters
from AnnieXMedia import app


@app.on_message(filters.command("meme"))
async def meme_command(client, message):
    args = message.text.split()
    category = args[1] if len(args) > 1 else ""

    api_url = f"https://meme-api.com/gimme/{category}" if category else "https://meme-api.com/gimme"

    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(api_url)
            try:
                data = response.json()
            except Exception:
                data = {}

        if response.status_code == 403 or ("message" in data and "Unable to Access Subreddit" in str(data.get("message"))):
            return await message.reply_text("❌ Memes from this category are not found. Please try a different one.")

        meme_url = data.get("url")
        title = data.get("title", "Meme")

        if not meme_url:
            return await message.reply_text("❌ Couldn't find a meme image. Please try again.")

        bot_info = await app.get_me()
        user_mention = message.from_user.mention if message.from_user else "User"

        caption = (
            f"{title}\n\n"
            f"Request by {user_mention}\n"
            f"Bot username: @{bot_info.username}"
        )

        try:
            await message.reply_photo(photo=meme_url, caption=caption)
        except Exception:
            await message.reply_text(f"{caption}\n\n{meme_url}")

    except Exception as e:
        print(f"Error fetching meme: {e}")
        await message.reply_text("Sorry, I couldn't fetch a meme at the moment.")
