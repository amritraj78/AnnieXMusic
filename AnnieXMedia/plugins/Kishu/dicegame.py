# Authored By Certified Coders © 2025
from pyrogram import filters
from AnnieXMedia import app

_GAME_EMOJIS = {
    "dice": "🎲",
    "dart": "🎯",
    "basket": "🏀",
    "jackpot": "🎰",
    "ball": "🎳",
    "football": "⚽",
}


def _get_mention(message):
    return message.from_user.mention if message.from_user else "Player"


@app.on_message(filters.command(list(_GAME_EMOJIS)))
async def play_emoji_game(bot, message):
    """Send a Telegram animated dice/game emoji and reply with the rolled score."""
    cmd = message.command[0].lower() if message.command else ""
    emoji = _GAME_EMOJIS.get(cmd)
    if not emoji:
        return
    try:
        sent = await bot.send_dice(message.chat.id, emoji)
        score = sent.dice.value if getattr(sent, "dice", None) else "?"
        await message.reply_text(f"{emoji} Hey {_get_mention(message)}, your score is: {score}")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


