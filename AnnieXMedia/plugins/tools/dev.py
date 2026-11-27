# Authored By Certified Coders © 2025
import html
import os
import re
import sys
import asyncio
import traceback
from io import StringIO
from time import time

from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import OWNER_ID
from AnnieXMedia import app
from AnnieXMedia.core.security import redact_secrets

_eval_lock = asyncio.Lock()


def _write_text_file(path: str, text: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out_file:
        out_file.write(text)


def _remove_file_if_exists(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


async def aexec(code, client, message):
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {a}" for a in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)


async def edit_or_reply(msg: Message, **kwargs):
    # Use edit_text if the message was sent by the bot itself; otherwise, use reply.
    func = msg.edit_text if msg.from_user and msg.from_user.is_self else msg.reply
    await func(**kwargs)


@app.on_edited_message(
    filters.command("eval")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command("eval")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def executor(client: Client, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")

    try:
        cmd = message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await message.delete()

    t1 = time()
    async with _eval_lock:
        old_stderr = sys.stderr
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()
        redirected_error = sys.stderr = StringIO()
        stdout, stderr, exc = None, None, None

        try:
            await aexec(cmd, client, message)
        except Exception:
            exc = traceback.format_exc()
        finally:
            stdout = redirected_output.getvalue()
            stderr = redirected_error.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    evaluation = "\n"
    if exc:
        evaluation += exc
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"

    evaluation = redact_secrets(evaluation)
    final_output = f"<b>⥤ ʀᴇsᴜʟᴛ :</b>\n<pre language='python'>{html.escape(evaluation)}</pre>"

    t2 = time()
    uid = message.from_user.id if message.from_user else 0
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⏳",
                    callback_data=f"runtime {round(t2 - t1, 3)} Seconds",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"forceclose abc|{uid}",
                ),
            ]
        ]
    )

    if len(final_output) > 4096:
        filename = f"cache/output_{message.chat.id}_{message.id}.txt"
        try:
            await asyncio.to_thread(_write_text_file, filename, str(evaluation))
            safe_cmd = html.escape(redact_secrets(cmd[:980]))
            await client.send_document(
                chat_id=message.chat.id,
                document=filename,
                caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{safe_cmd}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
                reply_markup=keyboard,
            )
            try:
                await message.delete()
            except Exception:
                pass
        finally:
            await asyncio.to_thread(_remove_file_if_exists, filename)
    else:
        await edit_or_reply(message, text=final_output, reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"^runtime\s+"))
async def runtime_func_cq(_, cq):
    parts = cq.data.split(None, 1)
    runtime = parts[1] if len(parts) > 1 else "0 Seconds"
    await cq.answer(runtime, show_alert=True)


@app.on_callback_query(filters.regex(r"^forceclose\s+"))
async def forceclose_command(_, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    parts = callback_data.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return
    _, user_id = parts[1].split("|", 1)
    target_uid = int(user_id) if user_id.isdigit() else 0
    if not CallbackQuery.from_user or CallbackQuery.from_user.id != target_uid:
        try:
            return await CallbackQuery.answer(
                "» ɪᴛ'ʟʟ ʙᴇ ʙᴇᴛᴛᴇʀ ɪғ ʏᴏᴜ sᴛᴀʏ ɪɴ ʏᴏᴜʀ ʟɪᴍɪᴛs ʙᴀʙʏ.", show_alert=True
            )
        except Exception:
            return
    if CallbackQuery.message:
        try:
            await CallbackQuery.message.delete()
        except Exception:
            pass
    try:
        await CallbackQuery.answer()
    except Exception:
        return


@app.on_edited_message(
    filters.command("sh")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command("sh")
    & filters.user(OWNER_ID)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴇxᴀᴍᴩʟᴇ :</b>\n/sh git pull")

    text = message.text.split(None, 1)[1]

    try:
        proc = await asyncio.create_subprocess_shell(
            text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
            output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return await edit_or_reply(message, text="<b>ERROR:</b> Command timed out after 60s.")
    except Exception as err:
        return await edit_or_reply(message, text=f"<b>ERROR :</b>\n<pre>{html.escape(str(err))}</pre>")

    output = redact_secrets(output)
    if not output.strip():
        output = "None"

    formatted = f"<b>OUTPUT :</b>\n<pre>{html.escape(output)}</pre>"
    if len(formatted) > 4096:
        out_path = f"cache/sh_output_{message.chat.id}_{message.id}.txt"
        try:
            await asyncio.to_thread(_write_text_file, out_path, output)
            await app.send_document(
                message.chat.id,
                out_path,
                reply_to_message_id=message.id,
                caption="<code>Output</code>",
            )
        finally:
            await asyncio.to_thread(_remove_file_if_exists, out_path)
    else:
        await edit_or_reply(message, text=formatted)

    await message.stop_propagation()
