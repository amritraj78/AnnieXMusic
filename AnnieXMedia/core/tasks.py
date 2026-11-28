# Authored By Certified Coders © 2025
import asyncio
from typing import Coroutine, Optional, Any

from AnnieXMedia.core.security import redact_secrets
from AnnieXMedia.logging import LOGGER

_log = LOGGER(__name__)
_bg_tasks: set[asyncio.Task] = set()


def _on_task_done(task: asyncio.Task) -> None:
    _bg_tasks.discard(task)
    if task.cancelled():
        return
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is None:
        return
    clean_err = redact_secrets(f"{type(exc).__name__}: {exc}")[:240]
    _log.warning(f"Background task {task.get_name()} failed: {clean_err}")
    try:
        from AnnieXMedia.core.self_heal import health_state

        health_state["unhandled_errors"] = int(health_state.get("unhandled_errors", 0)) + 1
        health_state["last_error"] = clean_err
    except Exception:
        pass


def spawn_task(
    coro: Coroutine[Any, Any, Any],
    *,
    name: Optional[str] = None,
) -> asyncio.Task:
    """Schedule a background asyncio task with strong reference retention and safe error logging."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(coro, name=name) if name else loop.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_on_task_done)
    return task


def active_task_count() -> int:
    """Return the number of tracked background tasks currently alive."""
    return len(_bg_tasks)
