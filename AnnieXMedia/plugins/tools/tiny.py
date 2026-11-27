# Authored By Certified Coders © 2025
import os
import asyncio
import subprocess
from PIL import Image
from pyrogram import Client, filters
from AnnieXMedia import app


def _process_tiny_image(ik: str, base_bg_path: str, out_file: str) -> bool:
    fil = None
    im1 = None
    im = None
    k = None
    back_im = None
    try:
        with Image.open(base_bg_path) as im1_orig:
            im1 = im1_orig.convert("RGBA")

        if ik.lower().endswith((".gif", ".mp4", ".webm")):
            fil = out_file + ".tmp.png"
            proc = subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", ik, "-vframes", "1", fil],
                capture_output=True,
                timeout=15,
            )
            if proc.returncode != 0 or not os.path.exists(fil):
                return False
            with Image.open(fil) as frame_orig:
                im = frame_orig.convert("RGBA")
        else:
            with Image.open(ik) as img_orig:
                im = img_orig.convert("RGBA")

        z, d = im.size
        if z == d:
            xxx, yyy = 200, 200
        else:
            t = max(z + d, 1)
            a = z / t
            b = d / t
            aa = (a * 100) - 50
            bb = (b * 100) - 50
            xxx = max(50, int(200 + 5 * aa))
            yyy = max(50, int(200 + 5 * bb))

        k = im.resize((xxx, yyy), Image.Resampling.LANCZOS)
        back_im = im1.copy()
        back_im.paste(k, (150, 0), k if k.mode == "RGBA" else None)
        back_im.save(out_file, "WEBP", quality=95)
        return True
    except Exception as e:
        print(f"[Tiny Error] {e}")
        return False
    finally:
        for obj in (im1, im, k, back_im):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        if fil and os.path.exists(fil):
            try:
                os.remove(fil)
            except Exception:
                pass


@app.on_message(filters.command("tiny"))
async def tiny_sticker(client, message):
    reply = message.reply_to_message
    if not (reply and reply.sticker):
        return await message.reply("Please reply to a sticker")

    kontol = await message.reply("Processing please wait...")
    os.makedirs("cache", exist_ok=True)
    ik = None
    out_file = f"cache/tiny_{message.chat.id}_{message.id}.webp"

    try:
        ik = await app.download_media(reply)
        if not ik or not os.path.exists(ik):
            return await kontol.edit_text("❌ Failed to download sticker.")

        base_png = "AnnieXMedia/assets/tiny.png"
        if not os.path.exists(base_png):
            return await kontol.edit_text("❌ Base asset missing.")

        success = await asyncio.to_thread(_process_tiny_image, ik, base_png, out_file)
        if success and os.path.exists(out_file):
            await app.send_document(message.chat.id, out_file, reply_to_message_id=message.id)
            await kontol.delete()
        else:
            await kontol.edit_text("❌ Failed to process sticker.")

    except Exception as e:
        await kontol.edit_text(f"❌ Error: {e}")

    finally:
        for path in (ik, out_file):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
