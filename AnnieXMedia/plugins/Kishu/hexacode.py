# Authored By Certified Coders © 2025
from pyrogram import filters
from AnnieXMedia import app
from config import BOT_USERNAME


def hex_to_text(hex_string):
    try:
        text = bytes.fromhex(hex_string).decode("utf-8")
        return text
    except Exception as e:
        return f"Error decoding hex: {str(e)}"


def text_to_hex(text):
    return " ".join(format(ord(char), "x") for char in text)


@app.on_message(filters.command("encode"))
async def encode_text(_, message):
    if len(message.command) > 1:
        input_text = " ".join(message.command[1:])[:1200]
        hex_representation = text_to_hex(input_text)
        safe_in = input_text.replace("`", "'")

        response_text = (
            f"𝗜𝗻𝗽𝘂𝘁 𝗧𝗲𝘅𝘁 ➪\n{safe_in}\n\n"
            f"𝗛𝗲𝘅 𝗥𝗲𝗽𝗿𝗲𝘀𝗲𝗻𝘁𝗮𝘁𝗶𝗼𝗻 ➪\n`{hex_representation}`\n\n"
            f"𝗕𝗬 ➪ @{BOT_USERNAME}"
        )

        await message.reply_text(response_text[:4096])
    else:
        await message.reply_text("Please provide text to encode.\nUsage: `/encode Hello`")


@app.on_message(filters.command("decode"))
async def decode_hex(_, message):
    if len(message.command) > 1:
        hex_input = "".join(message.command[1:]).replace(" ", "")[:3000]
        decoded_text = hex_to_text(hex_input).replace("`", "'")
        safe_hex = hex_input.replace("`", "'")

        response_text = (
            f"𝗛𝗲𝘅 𝗜𝗻𝗽𝘂𝘁 ➪\n{safe_hex}\n\n"
            f"𝗗𝗲𝗰𝗼𝗱𝗲𝗱 𝗧𝗲𝘅𝘁 ➪\n`{decoded_text}`\n\n"
            f"𝗕𝗬 ➪ @{BOT_USERNAME}"
        )

        await message.reply_text(response_text[:4096])
    else:
        await message.reply_text("Please provide hex to decode.\nUsage: `/decode 48656c6c6f`")
