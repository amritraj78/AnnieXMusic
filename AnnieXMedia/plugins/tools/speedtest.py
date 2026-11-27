# Authored By Certified Coders © 2025
import asyncio
import html

import speedtest
from pyrogram import filters
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.decorators.language import language


def run_speedtest():
    test = speedtest.Speedtest(secure=True)
    test.get_best_server()
    test.download()
    test.upload()
    try:
        test.results.share()
    except Exception:
        pass
    return test.results.dict()


@app.on_message(filters.command(["speedtest", "spt"]) & SUDOERS)
@language
async def speedtest_function(_, message: Message, lang):
    try:
        m = await message.reply_text(lang["server_11"])
        await m.edit_text(lang["server_12"])

        result = await asyncio.to_thread(run_speedtest)

        await m.edit_text(lang["server_13"])  #

        output = lang["server_15"].format(
            result["client"]["isp"],
            result["client"]["country"],
            result["server"]["name"],
            result["server"]["country"],
            result["server"]["cc"],
            result["server"]["sponsor"],
            result["server"]["latency"],
            result["ping"],
        )

        await m.edit_text(lang["server_14"])
        share_url = result.get("share")
        if share_url:
            try:
                await message.reply_photo(photo=share_url, caption=output)
            except Exception:
                await message.reply_text(output)
        else:
            await message.reply_text(output)
        try:
            await m.delete()
        except Exception:
            pass

    except Exception as e:
        await message.reply_text(f"<code>{html.escape(str(e))}</code>")
