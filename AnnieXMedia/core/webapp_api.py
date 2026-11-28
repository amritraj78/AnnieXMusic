# Authored By Certified Coders © 2025
import asyncio
import html
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote

from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup
from youtubesearchpython.aio import VideosSearch

import config
from AnnieXMedia import YouTube, app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.core.mongo import mongodb
from AnnieXMedia.core.prefetch import clean_song_title
from AnnieXMedia.core.self_heal import get_health_snapshot
from AnnieXMedia.core.track_cache import stats as cache_stats, track_cachedb
from AnnieXMedia.core.webapp_auth import verify_game_launch, verify_telegram_init_data
from AnnieXMedia.misc import SUDOERS, _boot_, db
from AnnieXMedia.utils.database import (
    autoplay_off,
    autoplay_on,
    get_active_chats,
    get_authuser_names,
    get_lang,
    get_loop,
    get_playtype,
    group_assistant,
    is_active_chat,
    is_autoplay,
    is_banned_user,
    is_gbanned_user,
    is_maintenance,
    is_music_playing,
    is_nonadmin_chat,
    music_off,
    music_on,
    set_loop,
)
from AnnieXMedia.utils.formatters import int_to_alpha, seconds_to_min
from AnnieXMedia.utils.inline import aq_markup, stream_markup
from AnnieXMedia.utils.security import fetch_url_limited, is_safe_http_url, redact_secrets
from AnnieXMedia.utils.stream.autoclear import auto_clean
from AnnieXMedia.utils.stream.queue import put_queue
from AnnieXMedia.utils.thumbnails import get_thumb
from config import BANNED_USERS, time_to_seconds
from strings import get_string

_YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_LRC_LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$")
_LYRICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
playlistsdb = mongodb.user_playlists
_RATE_BUCKETS: Dict[Tuple[Any, str], List[float]] = {}


def _check_rate_limit(subject: Any, bucket: str, limit: int, window_sec: float = 60.0) -> bool:
    """Return True if the request is within the per-subject sliding window quota."""
    now = time.monotonic()
    key = (str(subject), bucket)
    if len(_RATE_BUCKETS) > 2048:
        cutoff = now - 120.0
        for k in list(_RATE_BUCKETS.keys()):
            if not _RATE_BUCKETS[k] or _RATE_BUCKETS[k][-1] < cutoff:
                _RATE_BUCKETS.pop(k, None)
    hits = [ts for ts in _RATE_BUCKETS.get(key, ()) if (now - ts) < window_sec]
    if len(hits) >= limit:
        _RATE_BUCKETS[key] = hits
        return False
    hits.append(now)
    _RATE_BUCKETS[key] = hits
    return True

GAME_LABELS: Dict[str, str] = {
    "beats": "Beat Tiles",
    "snake": "Neon Snake",
    "flappy": "Flappy Beat",
    "breaker": "Brick Breaker",
    "g2048": "2048 Neon",
    "memory": "Memory Beat",
}
game_scoresdb = mongodb.game_scores
_bot_ready = lambda: bool(getattr(app, "id", 0))


def _display_name(user: Dict[str, Any]) -> str:
    first = str(user.get("first_name") or "").strip()
    last = str(user.get("last_name") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name[:48]
    uname = str(user.get("username") or "").strip()
    return f"@{uname}" if uname else f"Player {user.get('id', '')}"


def _auth_user(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    init_data = headers.get("x-telegram-init-data", "") or headers.get("authorization", "")
    if init_data.lower().startswith("tma "):
        init_data = init_data[4:].strip()
    return verify_telegram_init_data(init_data)


async def _is_chat_admin(chat_id: int, user_id: int) -> Tuple[bool, bool, str]:
    """Return (is_member, can_control, chat_title)."""
    is_sudo = user_id == config.OWNER_ID or user_id in SUDOERS
    title = f"Chat {chat_id}"
    if not _bot_ready():
        return is_sudo, is_sudo, title

    try:
        chat = await app.get_chat(chat_id)
        if getattr(chat, "title", None):
            title = str(chat.title)
    except Exception:
        pass

    try:
        member = await app.get_chat_member(chat_id, user_id)
    except Exception:
        return is_sudo, is_sudo, title

    if member.status in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT):
        return False, False, title
    if is_sudo or member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return True, True, title
    if await is_nonadmin_chat(chat_id):
        return True, True, title
    token = await int_to_alpha(user_id)
    if token in await get_authuser_names(chat_id):
        return True, True, title
    return True, False, title


async def get_leaderboard_data(
    game: str = "beats", limit: int = 15, user_id: Optional[int] = None
) -> Dict[str, Any]:
    g = game if game in GAME_LABELS else "beats"
    limit = max(1, min(int(limit), 50))
    top_rows: List[Dict[str, Any]] = []
    cursor = game_scoresdb.find({"game": g}).sort([("score", -1), ("updated_at", 1)]).limit(limit)
    idx = 0
    async for doc in cursor:
        idx += 1
        top_rows.append(
            {
                "rank": idx,
                "user_id": int(doc.get("user_id") or 0),
                "name": str(doc.get("name") or "Player")[:40],
                "username": str(doc.get("username") or ""),
                "score": int(doc.get("score") or 0),
            }
        )

    personal = None
    if user_id:
        my_doc = await game_scoresdb.find_one({"user_id": user_id, "game": g})
        if my_doc:
            my_score = int(my_doc.get("score") or 0)
            higher = await game_scoresdb.count_documents({"game": g, "score": {"$gt": my_score}})
            personal = {"score": my_score, "rank": higher + 1}

    return {
        "game": g,
        "label": GAME_LABELS[g],
        "scores": top_rows,
        "personal": personal,
    }


def _serialize_track(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_by = html.unescape(re.sub(r"<[^>]+>", "", str(item.get("by") or "User"))).strip()
    return {
        "title": str(item.get("title") or "Unknown"),
        "duration": str(item.get("dur") or "0:00"),
        "played": seconds_to_min(int(item.get("played") or 0)),
        "played_sec": int(item.get("played") or 0),
        "total_sec": max(int(item.get("seconds") or 0), 0),
        "by": raw_by or "User",
        "vidid": str(item.get("vidid") or ""),
        "streamtype": str(item.get("streamtype") or "audio"),
    }


async def _handle_overview(headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    user = auth["user"] if auth else None
    uid = int(user["id"]) if user else 0
    is_sudo = bool(uid and (uid == config.OWNER_ID or uid in SUDOERS))

    try:
        served_users = await mongodb.tgusersdb.count_documents({"user_id": {"$gt": 0}})
        served_chats = await mongodb.chats.count_documents({"chat_id": {"$lt": 0}})
    except Exception:
        served_users, served_chats = 0, 0

    active_ids = list(await get_active_chats())
    sessions: List[Dict[str, Any]] = []
    if user:
        extra = [config.LOGGER_ID] if (is_sudo and config.LOGGER_ID < 0) else []
        candidate_ids = [int(c) for c in list(dict.fromkeys(active_ids + extra))[:10]]
        checks = await asyncio.gather(
            *(_is_chat_admin(cid, uid) for cid in candidate_ids),
            return_exceptions=True,
        )
        for cid, chk in zip(candidate_ids, checks):
            if isinstance(chk, Exception):
                continue
            is_member, can_ctrl, chat_title = chk
            if not is_member:
                continue
            q_items = db.get(cid) or []
            is_active = cid in active_ids and bool(q_items)
            sessions.append(
                {
                    "chat_id": cid,
                    "title": chat_title,
                    "active": is_active,
                    "playing": await is_music_playing(cid) if is_active else False,
                    "loop": await get_loop(cid) if is_active else 0,
                    "autoplay": await is_autoplay(cid),
                    "current": _serialize_track(q_items[0]) if q_items else None,
                    "queue": [_serialize_track(t) for t in q_items[1:12]] if len(q_items) > 1 else [],
                    "queue_count": len(q_items),
                    "can_control": can_ctrl,
                }
            )

    try:
        cached_tracks = await track_cachedb.count_documents({})
    except Exception:
        cached_tracks = 0

    return 200, {
        "authenticated": bool(user),
        "user": {
            "id": uid,
            "name": _display_name(user),
            "username": user.get("username") or "",
            "is_sudo": is_sudo,
        }
        if user
        else None,
        "bot": {
            "name": getattr(app, "name", None) or config.BOT_NAME,
            "username": getattr(app, "username", None) or config.BOT_USERNAME,
            "support_channel": config.SUPPORT_CHANNEL,
            "support_chat": config.SUPPORT_CHAT,
            "owner_username": config.OWNER_USERNAME,
        },
        "stats": {
            "uptime_sec": int(time.time() - _boot_),
            "active_calls": len(active_ids),
            "served_chats": served_chats,
            "served_users": served_users,
            "cached_tracks": cached_tracks,
            "cache_hits": cache_stats["tg_hits"] + cache_stats["disk_hits"],
            "self_heal": get_health_snapshot(),
        },
        "sessions": sessions,
    }


async def _handle_search(query_str: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Open this Mini App inside Telegram to search and queue tracks."}
    uid = int(auth["user"]["id"])
    if not _check_rate_limit(uid, "search", 20, 60.0):
        return 429, {"error": "Too many search requests. Please wait a moment."}

    params = parse_qs(query_str)
    q = (params.get("q") or [""])[0].strip()
    if len(q) < 2 or len(q) > 120:
        return 400, {"error": "Provide a search query between 2 and 120 characters."}

    try:
        res = await VideosSearch(q, limit=6).next()
        raw_items = res.get("result") or []
    except Exception as exc:
        return 502, {"error": f"Search error: {redact_secrets(str(exc))[:200]}"}

    tracks = []
    for item in raw_items:
        vidid = str(item.get("id") or "")
        if not vidid:
            continue
        thumbs = item.get("thumbnails") or [{}]
        thumb = str(thumbs[-1].get("url") or "").split("?")[0] if thumbs else ""
        tracks.append(
            {
                "vidid": vidid,
                "title": str(item.get("title") or "Unknown"),
                "duration": str(item.get("duration") or "0:00"),
                "channel": str((item.get("channel") or {}).get("name") or "YouTube"),
                "views": str((item.get("viewCount") or {}).get("short") or ""),
                "thumb": thumb,
                "link": str(item.get("link") or f"https://www.youtube.com/watch?v={vidid}"),
            }
        )
    return 200, {"tracks": tracks}


async def _parse_target_chat(raw_target: Any) -> Optional[int]:
    if isinstance(raw_target, int):
        return raw_target
    s = str(raw_target or "").strip()
    if not s:
        return None
    if s.lstrip("-").isdigit():
        return int(s)
    if _bot_ready():
        try:
            chat = await app.get_chat(s.lstrip("@"))
            return int(chat.id)
        except Exception:
            return None
    return None


async def _verify_play_access(
    headers: Dict[str, str], raw_target_chat: Any
) -> Tuple[Optional[Tuple[Dict[str, Any], int, int]], Optional[Tuple[int, Dict[str, Any]]]]:
    """Validate auth, ban/maintenance state, rate quota, target group, and play permissions."""
    auth = _auth_user(headers)
    if not auth:
        return None, (401, {"error": "Telegram authentication required."})
    user = auth["user"]
    uid = int(user["id"])

    if uid in BANNED_USERS or await is_banned_user(uid) or await is_gbanned_user(uid):
        return None, (403, {"error": "You are banned from using this bot."})
    if not _check_rate_limit(uid, "play", 8, 60.0):
        return None, (429, {"error": "Too many play requests. Please slow down."})
    if await is_maintenance() is False and uid != config.OWNER_ID and uid not in SUDOERS:
        return None, (503, {"error": "Bot is currently in maintenance mode."})

    chat_id = await _parse_target_chat(raw_target_chat)
    if not chat_id or chat_id >= 0:
        return None, (400, {"error": "Valid group chat ID (-100...) is required."})

    is_member, can_ctrl, _ = await _is_chat_admin(chat_id, uid)
    if not is_member:
        return None, (403, {"error": "You must be a member of that group to queue music."})
    if await get_playtype(chat_id) != "Everyone" and not can_ctrl:
        return None, (403, {"error": "Only admins can play music in this group."})

    return (user, uid, chat_id), None


async def _send_now_playing_card(
    chat_id: int, vidid: str, safe_title: str, safe_dur: str, user_mention: str, _lang
) -> None:
    """Post the Now Playing stream photo card and attach its reference for live updates."""
    try:
        img = await get_thumb(vidid)
        bot_user = getattr(app, "username", None) or config.BOT_USERNAME
        cap = _lang["stream_1"].format(
            f"https://t.me/{bot_user}?start=info_{vidid}",
            safe_title[:23],
            safe_dur,
            user_mention,
        )
        run = await app.send_photo(
            chat_id,
            photo=img,
            caption=cap,
            reply_markup=InlineKeyboardMarkup(stream_markup(_lang, chat_id)),
        )
        if chat_id in db and db[chat_id]:
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
    except Exception:
        pass


async def _handle_play(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    ctx, err_resp = await _verify_play_access(headers, body.get("chat_id"))
    if err_resp:
        return err_resp
    user, uid, chat_id = ctx

    query = str(body.get("query") or "").strip()
    is_video = bool(body.get("video", False))
    hint_vidid = str(body.get("vidid") or "").strip()
    hint_title = str(body.get("title") or "").strip()

    if not query or len(query) > 200:
        return 400, {"error": "Provide a song name or YouTube URL."}

    if "://" in query:
        if not await YouTube.exists(query) or not await is_safe_http_url(query):
            return 400, {"error": "Only public YouTube URLs or song names are supported."}

    resolve_target = hint_vidid if _YOUTUBE_ID_RE.match(hint_vidid) else query
    try:
        details, vidid = await YouTube.track(resolve_target)
    except Exception:
        return 404, {"error": "Could not resolve track details."}

    title = str(details.get("title") or hint_title or "Unknown").title()
    duration_min = details.get("duration_min")
    if not duration_min:
        return 400, {"error": "Live streams are not supported from the Mini App."}
    dur_sec = time_to_seconds(duration_min)
    if dur_sec <= 0 or dur_sec > config.DURATION_LIMIT:
        return 400, {"error": f"Track exceeds duration limit ({config.DURATION_LIMIT_MIN} min)."}

    safe_title = html.escape(title)
    safe_dur = html.escape(str(duration_min))

    try:
        file_path, direct = await YouTube.download(
            vidid, None, video=is_video, videoid=vidid, title=title
        )
    except Exception as exc:
        return 502, {"error": f"Download error: {redact_secrets(str(exc))[:200]}"}

    if not file_path:
        return 502, {"error": "Failed to fetch track audio/video."}

    user_name = html.escape(_display_name(user))
    user_mention = f"<a href='tg://user?id={uid}'>{user_name}</a>"
    language = await get_lang(chat_id)
    _ = get_string(language)
    stream_label = "video" if is_video else "audio"
    thumb_url = str(details.get("thumb") or "")

    try:
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_mention,
                vidid,
                uid,
                stream_label,
            )
            pos = max(len(db.get(chat_id) or []) - 1, 1)
            try:
                await app.send_message(
                    chat_id=chat_id,
                    text=_["queue_4"].format(pos, safe_title[:27], safe_dur, user_mention),
                    reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
                )
            except Exception:
                pass
            return 200, {"ok": True, "status": "queued", "position": pos, "title": title}

        db[chat_id] = []
        await StreamController.join_call(
            chat_id, chat_id, file_path, video=is_video, image=thumb_url
        )
        await put_queue(
            chat_id,
            chat_id,
            file_path if direct else f"vid_{vidid}",
            title,
            duration_min,
            user_mention,
            vidid,
            uid,
            stream_label,
        )
        await _send_now_playing_card(chat_id, vidid, safe_title, safe_dur, user_mention, _)
        return 200, {"ok": True, "status": "playing", "title": title}
    except Exception as exc:
        return 400, {"error": redact_secrets(str(exc))[:240]}


async def _handle_control(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Telegram authentication required."}
    uid = int(auth["user"]["id"])
    if uid in BANNED_USERS or await is_banned_user(uid) or await is_gbanned_user(uid):
        return 403, {"error": "You are banned from using this bot."}
    if not _check_rate_limit(uid, "control", 30, 60.0):
        return 429, {"error": "Too many control requests. Please slow down."}
    if await is_maintenance() is False and uid != config.OWNER_ID and uid not in SUDOERS:
        return 503, {"error": "Bot is currently in maintenance mode."}

    chat_id = await _parse_target_chat(body.get("chat_id"))
    action = str(body.get("action") or "").strip().lower()

    if not chat_id or chat_id >= 0:
        return 400, {"error": "Valid group chat ID (-100...) is required."}
    is_member, can_ctrl, _ = await _is_chat_admin(chat_id, uid)
    if not is_member or not can_ctrl:
        return 403, {"error": "Admin rights required for this voice chat."}

    if action == "autoplay":
        val = body.get("value")
        cur = await is_autoplay(chat_id)
        target = (not cur) if val is None else bool(val)
        if target:
            await autoplay_on(chat_id)
        else:
            await autoplay_off(chat_id)
        return 200, {"ok": True, "action": "autoplay", "enabled": target}

    if not await is_active_chat(chat_id):
        return 404, {"error": "No active voice chat stream in that group."}

    try:
        if action == "pause":
            if await is_music_playing(chat_id):
                await music_off(chat_id)
                await StreamController.pause_stream(chat_id)
            return 200, {"ok": True, "action": "paused"}

        if action == "resume":
            if not await is_music_playing(chat_id):
                await music_on(chat_id)
                await StreamController.resume_stream(chat_id)
            return 200, {"ok": True, "action": "resumed"}

        if action == "skip":
            if not (db.get(chat_id) or []):
                return 404, {"error": "Queue is empty."}
            await set_loop(chat_id, 0)
            assistant = await group_assistant(StreamController, chat_id)
            await StreamController.play(assistant, chat_id)
            return 200, {"ok": True, "action": "skipped"}

        if action == "stop":
            await StreamController.stop_stream(chat_id)
            await set_loop(chat_id, 0)
            return 200, {"ok": True, "action": "stopped"}

        if action == "loop":
            try:
                val = max(0, min(10, int(body.get("value", 0))))
            except (TypeError, ValueError):
                return 400, {"error": "Invalid loop value."}
            await set_loop(chat_id, val)
            return 200, {"ok": True, "action": "loop", "value": val}

        if action == "seek":
            playing = db.get(chat_id) or []
            if not playing or not isinstance(playing[0], dict):
                return 404, {"error": "No active track to seek."}
            try:
                dur_sec = int(playing[0].get("seconds") or 0)
            except (TypeError, ValueError):
                dur_sec = 0
            if dur_sec <= 12:
                return 400, {"error": "Track duration is too short or live to seek."}
            try:
                target_sec = max(1, min(dur_sec - 5, int(body.get("value", 0))))
            except (TypeError, ValueError):
                return 400, {"error": "Invalid seek timestamp."}
            file_path = str(playing[0].get("file") or "")
            if "vid_" in file_path:
                n, stream_link = await YouTube.video(playing[0]["vidid"], True)
                if n == 0 or not stream_link:
                    return 400, {"error": "Could not resolve seekable stream."}
                file_path = stream_link
            if playing[0].get("speed_path"):
                file_path = str(playing[0]["speed_path"])
            if "index_" in file_path:
                file_path = str(playing[0]["vidid"])
            await StreamController.seek_stream(
                chat_id,
                file_path,
                seconds_to_min(target_sec),
                str(playing[0].get("dur") or seconds_to_min(dur_sec)),
                str(playing[0].get("streamtype") or "audio"),
            )
            playing[0]["played"] = target_sec
            return 200, {"ok": True, "action": "seek", "played_sec": target_sec}

        if action in ("remove", "move_top"):
            q_list = db.get(chat_id) or []
            try:
                q_idx = int(body.get("value", -1))
            except (TypeError, ValueError):
                return 400, {"error": "Invalid queue position."}
            if q_idx < 1 or q_idx >= len(q_list):
                return 404, {"error": "Queued track not found."}
            if action == "remove":
                removed = q_list.pop(q_idx)
                await auto_clean(removed)
                return 200, {"ok": True, "action": "removed"}
            if q_idx > 1:
                moved = q_list.pop(q_idx)
                q_list.insert(1, moved)
            return 200, {"ok": True, "action": "moved_top"}

        return 400, {"error": "Unsupported action."}
    except Exception as exc:
        return 500, {"error": redact_secrets(str(exc))[:240]}


async def _handle_game_score(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    game = str(body.get("game") or "").strip().lower()
    if game not in GAME_LABELS:
        return 400, {"error": "Unknown game."}
    try:
        score = int(body.get("score"))
    except (TypeError, ValueError):
        return 400, {"error": "Score must be an integer."}
    if score < 0 or score > 1_000_000:
        return 400, {"error": "Score out of valid bounds."}

    auth = _auth_user(headers)
    launch_payload = None
    if launch_tok := str(body.get("launch") or "").strip():
        launch_payload = verify_game_launch(launch_tok)

    if auth:
        user = auth["user"]
        uid = int(user["id"])
        name = _display_name(user)
        uname = str(user.get("username") or "")
    elif launch_payload:
        uid = int(launch_payload["user_id"])
        name = str(launch_payload.get("name") or f"Player {uid}")[:48]
        uname = str(launch_payload.get("username") or "")
    else:
        return 401, {"error": "Open inside Telegram to save leaderboard scores."}

    if not _check_rate_limit(uid, "score", 20, 60.0):
        return 429, {"error": "Too many score submissions. Please wait a moment."}

    now = int(time.time())
    await game_scoresdb.update_one(
        {"user_id": uid, "game": game},
        {
            "$max": {"score": score},
            "$set": {"name": name, "username": uname, "updated_at": now},
        },
        upsert=True,
    )

    # Also update native BotFather High Score card if opened from callback_game
    if launch_payload and _bot_ready():
        try:
            inline_id = launch_payload.get("inline_message_id")
            chat_id = launch_payload.get("chat_id")
            msg_id = launch_payload.get("message_id")
            if inline_id:
                await app.set_game_score(user_id=uid, score=score, inline_message_id=inline_id)
            elif chat_id and msg_id:
                await app.set_game_score(
                    user_id=uid, score=score, chat_id=int(chat_id), message_id=int(msg_id)
                )
        except Exception:
            pass

    lb = await get_leaderboard_data(game, limit=15, user_id=uid)
    return 200, {"ok": True, **lb}


async def _handle_lyrics(query_str: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    rl_subj = int(auth["user"]["id"]) if auth else (headers.get("x-client-ip") or "guest")
    if not _check_rate_limit(rl_subj, "lyrics", 30, 60.0):
        return 429, {"error": "Too many lyrics requests. Wait a moment."}

    params = parse_qs(query_str)
    raw_title = (params.get("title") or [""])[0].strip()
    if len(raw_title) < 2 or len(raw_title) > 150:
        return 400, {"error": "Provide a valid track title."}

    cleaned = clean_song_title(raw_title)
    cache_key = cleaned.lower()
    now = time.time()
    if cached := _LYRICS_CACHE.get(cache_key):
        if now - cached[0] < 3600:
            return 200, cached[1]
        _LYRICS_CACHE.pop(cache_key, None)

    url = f"https://lrclib.net/api/search?q={quote(cleaned)}"
    ok, status, _, body_bytes = await fetch_url_limited(
        url,
        max_bytes=512 * 1024,
        timeout=6.0,
        headers={"User-Agent": "AnnieXMusic/2.0 (https://t.me/ritulavbot)"},
    )
    if not ok or status >= 400 or not body_bytes:
        return 200, {"ok": True, "found": False, "title": cleaned, "lines": [], "plain": ""}

    try:
        items = json.loads(body_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        items = []

    best = None
    if isinstance(items, list):
        best = next(
            (it for it in items if isinstance(it, dict) and (it.get("syncedLyrics") or it.get("plainLyrics"))),
            None,
        )
    if not best:
        res = {"ok": True, "found": False, "title": cleaned, "lines": [], "plain": ""}
        if len(_LYRICS_CACHE) >= 256:
            _LYRICS_CACHE.pop(next(iter(_LYRICS_CACHE)), None)
        _LYRICS_CACHE[cache_key] = (now, res)
        return 200, res

    synced_raw = str(best.get("syncedLyrics") or "")
    lines: List[Dict[str, Any]] = []
    for raw_ln in synced_raw.splitlines():
        m = _LRC_LINE_RE.match(raw_ln.strip())
        if not m:
            continue
        mins = int(m.group(1))
        secs = int(m.group(2))
        frac_str = m.group(3) or "0"
        frac = int(frac_str) / (10 ** len(frac_str))
        txt = m.group(4).strip()
        if txt:
            lines.append({"time_sec": round(mins * 60 + secs + frac, 2), "text": txt})

    plain_raw = str(best.get("plainLyrics") or "").strip()
    if not plain_raw and lines:
        plain_raw = "\n".join(x["text"] for x in lines)

    res = {
        "ok": True,
        "found": bool(lines or plain_raw),
        "title": str(best.get("trackName") or cleaned),
        "artist": str(best.get("artistName") or ""),
        "synced": bool(lines),
        "lines": lines[:200],
        "plain": plain_raw[:6000],
    }
    if len(_LYRICS_CACHE) >= 256:
        _LYRICS_CACHE.pop(next(iter(_LYRICS_CACHE)), None)
    _LYRICS_CACHE[cache_key] = (now, res)
    return 200, res


async def _handle_playlists_get(headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Open inside Telegram to access your Saved Tracks."}
    uid = int(auth["user"]["id"])
    doc = await playlistsdb.find_one({"user_id": uid})
    tracks = list((doc or {}).get("tracks") or [])[:50]
    return 200, {"ok": True, "tracks": tracks}


async def _handle_playlist_save(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Telegram authentication required."}
    uid = int(auth["user"]["id"])
    if not _check_rate_limit(uid, "pl_write", 30, 60.0):
        return 429, {"error": "Too many playlist edits. Slow down."}

    vidid = str(body.get("vidid") or "").strip()
    title = str(body.get("title") or "").strip()[:120]
    duration = str(body.get("duration") or "0:00").strip()[:16]
    thumb = str(body.get("thumb") or "").strip()[:260]
    if not _YOUTUBE_ID_RE.match(vidid) or not title:
        return 400, {"error": "Valid YouTube track vidid and title are required."}

    if not thumb or not await is_safe_http_url(thumb):
        thumb = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"

    doc = await playlistsdb.find_one({"user_id": uid})
    tracks = [t for t in ((doc or {}).get("tracks") or []) if isinstance(t, dict) and t.get("vidid") != vidid]
    tracks.insert(
        0,
        {
            "vidid": vidid,
            "title": title,
            "duration": duration,
            "thumb": thumb,
            "link": f"https://www.youtube.com/watch?v={vidid}",
        },
    )
    tracks = tracks[:50]
    await playlistsdb.update_one(
        {"user_id": uid},
        {"$set": {"tracks": tracks, "updated_at": int(time.time())}},
        upsert=True,
    )
    return 200, {"ok": True, "tracks": tracks}


async def _handle_playlist_delete(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Telegram authentication required."}
    uid = int(auth["user"]["id"])
    vidid = str(body.get("vidid") or "").strip()
    if not _YOUTUBE_ID_RE.match(vidid):
        return 400, {"error": "Valid track vidid is required."}

    doc = await playlistsdb.find_one({"user_id": uid})
    tracks = [t for t in ((doc or {}).get("tracks") or []) if isinstance(t, dict) and t.get("vidid") != vidid]
    await playlistsdb.update_one(
        {"user_id": uid},
        {"$set": {"tracks": tracks, "updated_at": int(time.time())}},
        upsert=True,
    )
    return 200, {"ok": True, "tracks": tracks}


async def _handle_playlist_play(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    ctx, err_resp = await _verify_play_access(headers, body.get("chat_id"))
    if err_resp:
        return err_resp
    user, uid, chat_id = ctx

    doc = await playlistsdb.find_one({"user_id": uid})
    saved_tracks = list((doc or {}).get("tracks") or [])[:10]
    if not saved_tracks:
        return 404, {"error": "Your Saved Library is empty."}

    user_name = html.escape(_display_name(user))
    user_mention = f"<a href='tg://user?id={uid}'>{user_name}</a>"
    _ = get_string(await get_lang(chat_id))
    queued_count = 0

    for item in saved_tracks:
        vid = str(item.get("vidid") or "").strip()
        if not _YOUTUBE_ID_RE.match(vid):
            continue
        t_title = str(item.get("title") or vid).title()
        t_dur = str(item.get("duration") or "3:30")
        if await is_active_chat(chat_id):
            await put_queue(chat_id, chat_id, f"vid_{vid}", t_title, t_dur, user_mention, vid, uid, "audio")
            queued_count += 1
        else:
            file_path, direct = await YouTube.download(vid, None, video=False, videoid=vid, title=t_title)
            if not file_path:
                continue
            db[chat_id] = []
            await StreamController.join_call(chat_id, chat_id, file_path, video=False)
            await put_queue(
                chat_id,
                chat_id,
                file_path if direct else f"vid_{vid}",
                t_title,
                t_dur,
                user_mention,
                vid,
                uid,
                "audio",
            )
            await _send_now_playing_card(
                chat_id, vid, html.escape(t_title), html.escape(t_dur), user_mention, _
            )
            queued_count += 1

    if queued_count == 0:
        return 502, {"error": "Could not start saved playlist tracks."}
    return 200, {"ok": True, "queued_count": queued_count}


async def handle_api_request(
    method: str,
    path: str,
    query_str: str,
    headers: Dict[str, str],
    body_bytes: bytes,
) -> Tuple[int, Dict[str, Any]]:
    body: Dict[str, Any] = {}
    if method == "POST":
        try:
            parsed = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            if not isinstance(parsed, dict):
                return 400, {"error": "JSON object body expected."}
            body = parsed
        except Exception:
            return 400, {"error": "Invalid JSON body."}

    if path == "/api/overview" and method == "GET":
        return await _handle_overview(headers)
    if path == "/api/search" and method == "GET":
        return await _handle_search(query_str, headers)
    if path == "/api/play" and method == "POST":
        return await _handle_play(headers, body)
    if path == "/api/control" and method == "POST":
        return await _handle_control(headers, body)
    if path == "/api/lyrics" and method == "GET":
        return await _handle_lyrics(query_str, headers)
    if path == "/api/playlists" and method == "GET":
        return await _handle_playlists_get(headers)
    if path == "/api/playlists/save" and method == "POST":
        return await _handle_playlist_save(headers, body)
    if path == "/api/playlists/delete" and method == "POST":
        return await _handle_playlist_delete(headers, body)
    if path == "/api/playlists/play" and method == "POST":
        return await _handle_playlist_play(headers, body)
    if path == "/api/games/leaderboard" and method == "GET":
        params = parse_qs(query_str)
        game = (params.get("game") or ["beats"])[0]
        auth = _auth_user(headers)
        uid = int(auth["user"]["id"]) if auth else None
        if not uid and (lt := (params.get("launch") or [""])[0]):
            if lp := verify_game_launch(lt):
                uid = int(lp["user_id"])
        return 200, await get_leaderboard_data(game, limit=15, user_id=uid)
    if path == "/api/games/score" and method == "POST":
        return await _handle_game_score(headers, body)

    return 404, {"error": "API endpoint not found."}
