# Authored By Certified Coders © 2025
import asyncio
import os
from pyrogram import filters
from pyrogram.types import Message
from AnnieXMedia import app
from AnnieXMedia.core.security import redact_secrets

MAX_SIZE_MB = 50
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


async def _run_ffmpeg(*args: str, timeout: float = 60.0) -> tuple[bool, bool]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass
        return False, True
    return proc.returncode == 0, False


@app.on_message(filters.command("extract") & filters.reply)
async def extract_media(_, message: Message):
    replied = message.reply_to_message

    if not (replied and replied.video):
        return await message.reply_text("❌ Please reply to a *video* message.")
    if len(message.command) < 2:
        return await message.reply_text("ℹ️ Use `/extract audio` or `/extract video`.")

    if replied.video.file_size and replied.video.file_size > MAX_SIZE_BYTES:
        return await message.reply_text(
            f"🚫 File is too large ({replied.video.file_size // (1024*1024)} MB).\n"
            f"Maximum allowed size is {MAX_SIZE_MB} MB."
        )

    command = message.command[1].lower()
    if command not in ("audio", "video"):
        return await message.reply_text("❌ Invalid command. Use `/extract audio` or `/extract video`.")

    processing_msg = await message.reply_text("🔧 Processing video…")

    os.makedirs("cache", exist_ok=True)
    file_path = os.path.abspath(f"cache/media_input_{message.chat.id}_{message.id}.mp4")
    output_audio = os.path.abspath(f"cache/extracted_audio_{message.chat.id}_{message.id}.mp3")
    output_video = os.path.abspath(f"cache/extracted_video_{message.chat.id}_{message.id}.mp4")
    downloaded = None

    try:
        downloaded = await replied.download(file_name=file_path)
        actual_input = downloaded if downloaded and os.path.exists(downloaded) else file_path
        if not actual_input or not os.path.exists(actual_input):
            return await processing_msg.edit_text("❌ Failed to download video file.")

        if command == "audio":
            ok, timed_out = await _run_ffmpeg(
                "-i", actual_input, "-vn", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k", output_audio
            )
            if timed_out:
                return await processing_msg.edit_text("❌ FFmpeg processing timed out.")
            if ok and os.path.exists(output_audio):
                await app.send_audio(message.chat.id, output_audio, caption="🎧 Audio extracted.")
            else:
                return await processing_msg.edit_text("❌ Failed to extract audio from this video.")

        elif command == "video":
            ok, timed_out = await _run_ffmpeg(
                "-i", actual_input, "-c", "copy", "-an", output_video
            )
            if timed_out:
                return await processing_msg.edit_text("❌ FFmpeg processing timed out.")
            if ok and os.path.exists(output_video):
                await app.send_video(message.chat.id, output_video, caption="🎞️ Video with no audio.")
            else:
                return await processing_msg.edit_text("❌ FFmpeg processing failed.")

    except Exception as e:
        safe_err = redact_secrets(str(e)).replace("`", "'")
        await message.reply_text(f"❌ Error: `{safe_err}`")

    finally:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        for path in (downloaded, file_path, output_audio, output_video):
            if path and os.path.exists(path):
                try:
                    await asyncio.to_thread(os.remove, path)
                except Exception:
                    pass
