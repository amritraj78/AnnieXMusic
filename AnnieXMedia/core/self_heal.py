# Authored By Certified Coders © 2025
"""Self-healing watchdog, error auto-recovery, and keep-alive persistence engine."""
import asyncio
import contextlib
import os
import time
from typing import Any, Dict, Optional

import aiohttp

import config
from AnnieXMedia.core.dir import prune_storage_cache
from AnnieXMedia.core.http_pool import get_http_session
from AnnieXMedia.core.mongo import _mongo_async_
from AnnieXMedia.core.security import is_safe_http_url, redact_secrets
from AnnieXMedia.logging import LOGGER

log = LOGGER(__name__)

_START_TS = time.time()
_MAX_BOT_DOWN_STREAK = 6
_STALL_OVERTIME_SEC = 45.0
_GHOST_CONFIRM_TICKS = 2
_ALERT_COOLDOWN_SEC = 300.0
_COOKIE_REFRESH_SEC = 21600.0
_COOKIE_ERR_COOLDOWN = 900.0

_bot_down_streak = 0
_last_alert_ts = 0.0
_last_cookie_refresh_ts = 0.0
_last_prune_ts = 0.0
_download_failures = 0

_ghost_ticks: Dict[int, int] = {}
_overtime_since: Dict[int, float] = {}

_tasks: list[asyncio.Task] = []

health_state: Dict[str, Any] = {
    "db_ok": True,
    "bot_connected": True,
    "assistants_online": 0,
    "recoveries": 0,
    "ghost_calls_healed": 0,
    "stalled_calls_healed": 0,
    "cookie_refreshes": 0,
    "unhandled_errors": 0,
    "last_keepalive_ok": True,
    "last_keepalive_at": 0,
    "last_check_at": 0,
    "last_error": "",
}


def note_download_failure() -> None:
    """Increment failure counter so watchdog triggers early cookie/cache recovery."""
    global _download_failures
    _download_failures += 1


def reset_download_failures() -> None:
    global _download_failures
    _download_failures = 0


def get_health_snapshot() -> Dict[str, Any]:
    return {
        "uptime_sec": int(time.time() - _START_TS),
        "db_ok": bool(health_state["db_ok"]),
        "bot_connected": bool(health_state["bot_connected"]),
        "assistants_online": int(health_state["assistants_online"]),
        "recoveries": int(health_state["recoveries"]),
        "ghost_calls_healed": int(health_state["ghost_calls_healed"]),
        "stalled_calls_healed": int(health_state["stalled_calls_healed"]),
        "unhandled_errors": int(health_state["unhandled_errors"]),
        "last_keepalive_ok": bool(health_state["last_keepalive_ok"]),
        "last_check_at": int(health_state["last_check_at"]),
    }


async def _notify_logger(msg: str) -> None:
    global _last_alert_ts
    now = time.time()
    if now - _last_alert_ts < _ALERT_COOLDOWN_SEC or not config.LOGGER_ID:
        return
    try:
        from AnnieXMedia import app

        if getattr(app, "id", 0) and getattr(app, "is_connected", False):
            _last_alert_ts = now
            await app.send_message(config.LOGGER_ID, msg[:3800])
    except Exception:
        pass


def install_loop_exception_handler(loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Prevent uncaught task exceptions from destabilizing the event loop."""
    target_loop = loop or asyncio.get_running_loop()

    def _handler(_loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
        health_state["unhandled_errors"] += 1
        exc = context.get("exception")
        raw_msg = str(exc or context.get("message") or "Unknown async error")
        clean_msg = redact_secrets(raw_msg)[:300]
        health_state["last_error"] = clean_msg
        if isinstance(exc, asyncio.CancelledError):
            return
        log.warning(f"🛡️ Self-Heal caught async error: {clean_msg}")

    target_loop.set_exception_handler(_handler)


async def _check_and_heal_bot() -> bool:
    global _bot_down_streak
    from AnnieXMedia import app

    try:
        if not getattr(app, "is_connected", False):
            log.warning("🛡️ Bot client disconnected; attempting reconnect...")
            await asyncio.wait_for(app.connect(), timeout=12.0)
            health_state["recoveries"] += 1
        me = await asyncio.wait_for(app.get_me(), timeout=10.0)
        if me:
            app.id = me.id
            app.username = me.username
        _bot_down_streak = 0
        health_state["bot_connected"] = True
        return True
    except Exception as exc:
        _bot_down_streak += 1
        health_state["bot_connected"] = False
        health_state["last_error"] = redact_secrets(str(exc))[:240]
        log.warning(f"🛡️ Bot health probe failed ({_bot_down_streak}/{_MAX_BOT_DOWN_STREAK}): {health_state['last_error']}")
        if _bot_down_streak >= _MAX_BOT_DOWN_STREAK:
            log.error("🛡️ Bot stayed unrecoverable across max retries; exiting cleanly for supervisor restart.")
            os._exit(1)
        return False


async def _check_and_heal_assistants() -> int:
    from AnnieXMedia import userbot

    online = 0
    for idx, ub in enumerate((userbot.one, userbot.two, userbot.three, userbot.four, userbot.five), 1):
        if ub is None:
            continue
        try:
            if getattr(ub, "is_connected", False):
                online += 1
            else:
                log.warning(f"🛡️ Assistant {idx} disconnected; reconnecting...")
                await asyncio.wait_for(ub.connect(), timeout=12.0)
                health_state["recoveries"] += 1
                online += 1
        except Exception as exc:
            log.warning(f"🛡️ Assistant {idx} reconnect skipped: {redact_secrets(str(exc))[:160]}")
    health_state["assistants_online"] = online
    return online


async def _heal_calls_and_queues() -> None:
    from AnnieXMedia.core.call import StreamController, _clear_
    from AnnieXMedia.misc import db
    from AnnieXMedia.utils.database import get_active_chats, group_assistant, is_music_playing

    now = time.time()
    active_ids = set(await get_active_chats())

    # 1. Clean ghost active chats that have no queue and no active PyTgCalls session
    for cid in list(active_ids):
        has_q = bool(db.get(cid))
        in_calls = cid in StreamController.active_calls
        if not has_q and not in_calls:
            _ghost_ticks[cid] = _ghost_ticks.get(cid, 0) + 1
            if _ghost_ticks[cid] >= _GHOST_CONFIRM_TICKS:
                _ghost_ticks.pop(cid, None)
                with contextlib.suppress(Exception):
                    await _clear_(cid)
                    health_state["ghost_calls_healed"] += 1
                    health_state["recoveries"] += 1
                    log.info(f"🛡️ Cleared ghost active call state for chat {cid}")
        else:
            _ghost_ticks.pop(cid, None)

    # 2. Heal streams stalled past song end where StreamEnded update was dropped
    for cid in list(active_ids):
        playing = db.get(cid)
        if not playing or not isinstance(playing, list) or not isinstance(playing[0], dict):
            _overtime_since.pop(cid, None)
            continue
        try:
            if not await is_music_playing(cid):
                _overtime_since.pop(cid, None)
                continue
            dur = int(playing[0].get("seconds") or 0)
            played = int(playing[0].get("played") or 0)
        except (TypeError, ValueError):
            _overtime_since.pop(cid, None)
            continue

        if dur > 0 and played >= dur:
            since = _overtime_since.setdefault(cid, now)
            if now - since >= _STALL_OVERTIME_SEC:
                _overtime_since.pop(cid, None)
                try:
                    assistant = await group_assistant(StreamController, cid)
                    await StreamController.play(assistant, cid)
                    health_state["stalled_calls_healed"] += 1
                    health_state["recoveries"] += 1
                    log.warning(f"🛡️ Healed stalled stream transition in chat {cid}")
                    await _notify_logger(f"🛡️ <b>Self-Heal:</b> Recovered stalled stream in <code>{cid}</code>.")
                except Exception as exc:
                    log.warning(f"🛡️ Failed stalled stream recovery in {cid}: {redact_secrets(str(exc))[:160]}")
        else:
            _overtime_since.pop(cid, None)

    # Prune stale tracking keys for chats no longer active
    for cid in list(_ghost_ticks.keys()):
        if cid not in active_ids:
            _ghost_ticks.pop(cid, None)
    for cid in list(_overtime_since.keys()):
        if cid not in active_ids:
            _overtime_since.pop(cid, None)


async def _refresh_cookies_if_needed() -> None:
    global _last_cookie_refresh_ts, _download_failures
    if not config.COOKIE_URL:
        return
    now = time.time()
    due_periodic = (now - _last_cookie_refresh_ts) >= _COOKIE_REFRESH_SEC
    due_errors = _download_failures >= 3 and (now - _last_cookie_refresh_ts) >= _COOKIE_ERR_COOLDOWN
    if not (due_periodic or due_errors):
        return
    try:
        from AnnieXMedia.utils.cookie_handler import fetch_and_store_cookies

        await fetch_and_store_cookies()
        _last_cookie_refresh_ts = now
        _download_failures = 0
        health_state["cookie_refreshes"] += 1
        log.info("🛡️ YouTube cookies refreshed automatically.")
    except Exception as exc:
        _last_cookie_refresh_ts = now
        log.debug(f"🛡️ Cookie auto-refresh skipped: {redact_secrets(str(exc))[:160]}")


async def run_heal_cycle() -> None:
    """Execute one non-blocking self-healing pass across DB, clients, calls, cookies, and disk."""
    global _last_prune_ts
    health_state["last_check_at"] = int(time.time())

    try:
        await asyncio.wait_for(_mongo_async_.admin.command("ping"), timeout=6.0)
        health_state["db_ok"] = True
    except Exception as exc:
        health_state["db_ok"] = False
        health_state["last_error"] = redact_secrets(str(exc))[:200]
        log.warning(f"🛡️ MongoDB health check failed: {health_state['last_error']}")

    await _check_and_heal_bot()
    await _check_and_heal_assistants()
    with contextlib.suppress(Exception):
        await _heal_calls_and_queues()
    with contextlib.suppress(Exception):
        await _refresh_cookies_if_needed()

    now = time.time()
    if now - _last_prune_ts >= 600:
        _last_prune_ts = now
        with contextlib.suppress(Exception):
            await asyncio.to_thread(prune_storage_cache)


async def _watchdog_loop() -> None:
    interval = max(20, int(getattr(config, "SELF_HEAL_INTERVAL", 45)))
    while True:
        await asyncio.sleep(interval)
        try:
            await run_heal_cycle()
        except Exception as exc:
            health_state["last_error"] = redact_secrets(str(exc))[:200]
            log.warning(f"🛡️ Self-heal loop iteration error: {health_state['last_error']}")


async def _keep_alive_loop() -> None:
    interval = max(60, int(getattr(config, "KEEP_ALIVE_INTERVAL", 240)))
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        port = 8080
    local_url = f"http://127.0.0.1:{port}/health"
    public_url = f"{config.WEBAPP_URL}/health" if str(config.WEBAPP_URL).startswith("https://") else ""

    while True:
        await asyncio.sleep(interval)
        try:
            session = await get_http_session()
            async with session.get(local_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                ok_local = resp.status == 200
            if public_url and await is_safe_http_url(public_url):
                with contextlib.suppress(Exception):
                    async with session.get(public_url, timeout=aiohttp.ClientTimeout(total=10)):
                        pass
            health_state["last_keepalive_ok"] = ok_local
            health_state["last_keepalive_at"] = int(time.time())
        except Exception:
            health_state["last_keepalive_ok"] = False


def start_self_heal() -> None:
    """Start watchdog & keep-alive background tasks and attach loop exception guard."""
    if _tasks:
        return
    loop = asyncio.get_running_loop()
    install_loop_exception_handler(loop)
    _tasks.append(loop.create_task(_watchdog_loop(), name="self-heal-watchdog"))
    _tasks.append(loop.create_task(_keep_alive_loop(), name="self-heal-keepalive"))
    log.info("🛡️ Self-Healing Watchdog & Keep-Alive Engine started.")


async def stop_self_heal() -> None:
    for t in list(_tasks):
        t.cancel()
    for t in list(_tasks):
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    _tasks.clear()
