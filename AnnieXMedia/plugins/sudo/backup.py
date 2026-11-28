# Authored By Certified Coders © 2025

import asyncio
import json
import os
import tempfile
import zipfile
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message

from AnnieXMedia import app
from AnnieXMedia.core.dir import BACKUP_DIR
from AnnieXMedia.core.mongo import mongodb
from AnnieXMedia.core.tasks import spawn_task
from AnnieXMedia.logging import LOGGER
from AnnieXMedia.utils.security import redact_secrets
from config import LOGGER_ID, OWNER_ID

_backup_lock = asyncio.Lock()


def _write_json(path: str, data: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


async def _dump_collection(collection, path: str):
    data = []
    async for doc in collection.find({}):
        doc.pop("_id", None)
        for key, value in list(doc.items()):
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
        data.append(doc)
    if data:
        await asyncio.to_thread(_write_json, path, data)


def _build_zip_archive(zip_path: str, source_dir: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                fp = os.path.join(root, file)
                arc = os.path.join("Annie", os.path.relpath(fp, source_dir))
                zf.write(fp, arc)


def _prepare_backup_dir() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for fname in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, fname)
        if os.path.isfile(fpath) and fname.endswith(".zip"):
            try:
                os.remove(fpath)
            except Exception:
                pass


def _remove_file(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


async def _create_backup_zip() -> str:
    async with _backup_lock:
        LOGGER(__name__).info("🗂️ Starting backup process for all collections…")
        await asyncio.to_thread(_prepare_backup_dir)

        collections = await mongodb.list_collection_names()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"AnnieXMedia_Backup_{timestamp}.zip"
        zip_path = os.path.join(BACKUP_DIR, zip_name)

        with tempfile.TemporaryDirectory(dir=BACKUP_DIR, prefix="tmp_") as tmp_dir:
            tasks = [
                _dump_collection(mongodb[coll], os.path.join(tmp_dir, f"{coll}.json"))
                for coll in collections
            ]
            await asyncio.gather(*tasks)

            LOGGER(__name__).info(f"📦 Creating backup archive: {zip_name}")
            await asyncio.to_thread(_build_zip_archive, zip_path, tmp_dir)

        return zip_path


async def _send_backup(zip_path: str, chat_id: int, caption: str):
    try:
        await app.send_document(chat_id=chat_id, document=zip_path, caption=caption)
    finally:
        await asyncio.to_thread(_remove_file, zip_path)


@app.on_message(filters.command("backup") & filters.user(OWNER_ID))
async def manual_backup(_: Client, message: Message):
    processing = await message.reply_text(
        "🔐 **Starting Backup…**\n"
        "__Please wait while we securely export your database.__ 🚀"
    )
    try:
        zip_path = await _create_backup_zip()
        caption = (
            "✅ **Backup Successfully Completed!**\n"
            "__Your MongoDB database has been exported.__ 📁✨\n\n"
            f"**File:** `{os.path.basename(zip_path)}`"
        )
        await _send_backup(zip_path, message.chat.id, caption)
        try:
            await processing.delete()
        except Exception:
            pass
    except Exception as e:
        safe_err = redact_secrets(str(e))
        await processing.edit_text(
            "❌ **Backup Failed!**\n"
            f"**Error:** `{safe_err}`"
        )
        LOGGER(__name__).error(f"Manual backup failed: {safe_err}")


async def daily_backup_task():
    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            await asyncio.sleep((target - now).total_seconds())
            zip_path = await _create_backup_zip()
            caption = (
                "🕛 **Daily Backup — Completed☑️**\n"
                "__Your automatic full database backup is ready.__ 🔒📦"
            )
            await _send_backup(zip_path, LOGGER_ID, caption)
            LOGGER(__name__).info("Daily backup sent to LOGGER_ID.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            LOGGER(__name__).error(f"Daily backup failed: {redact_secrets(str(e))}")
            await asyncio.sleep(60)


try:
    spawn_task(daily_backup_task(), name="daily_backup_task")
except RuntimeError:
    pass
