# Authored By Certified Coders © 2025
import html
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs

from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup
from youtubesearchpython.aio import VideosSearch

import config
from AnnieXMedia import YouTube, app
from AnnieXMedia.core.call import StreamController
from AnnieXMedia.core.mongo import mongodb
from AnnieXMedia.core.webapp_auth import verify_game_launch, verify_telegram_init_data
from AnnieXMedia.misc import SUDOERS, _boot_, db
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_lang,
    get_loop,
    get_playtype,
    group_assistant,
    is_active_chat,
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
from AnnieXMedia.utils.stream.queue import put_queue
from AnnieXMedia.utils.thumbnails import get_thumb
from config import BANNED_USERS, time_to_seconds
from strings import get_string

_YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

GAME_LABELS: Dict[str, str] = {
    "beats": "Beat Tiles",
    "snake": "Neon Snake",
    "flappy": "Flappy Beat",
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
    return {
        "title": str(item.get("title") or "Unknown"),
        "duration": str(item.get("dur") or "0:00"),
        "played": seconds_to_min(int(item.get("played") or 0)),
        "played_sec": int(item.get("played") or 0),
        "total_sec": max(int(item.get("seconds") or 0), 0),
        "by": str(item.get("by") or "User"),
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
        candidate_ids = list(dict.fromkeys(active_ids + ([config.LOGGER_ID] if config.LOGGER_ID < 0 else [])))
        for cid in candidate_ids[:10]:
            is_member, can_ctrl, chat_title = await _is_chat_admin(int(cid), uid)
            if not is_member:
                continue
            q_items = db.get(int(cid)) or []
            is_active = int(cid) in active_ids and bool(q_items)
            sessions.append(
                {
                    "chat_id": int(cid),
                    "title": chat_title,
                    "active": is_active,
                    "playing": await is_music_playing(int(cid)) if is_active else False,
                    "loop": await get_loop(int(cid)) if is_active else 0,
                    "current": _serialize_track(q_items[0]) if q_items else None,
                    "queue": [_serialize_track(t) for t in q_items[1:12]] if len(q_items) > 1 else [],
                    "queue_count": len(q_items),
                    "can_control": can_ctrl,
                }
            )

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
        },
        "sessions": sessions,
    }


async def _handle_search(query_str: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    if not _auth_user(headers):
        return 401, {"error": "Open this Mini App inside Telegram to search and queue tracks."}

    params = parse_qs(query_str)
    q = (params.get("q") or [""])[0].strip()
    if len(q) < 2 or len(q) > 120:
        return 400, {"error": "Provide a search query between 2 and 120 characters."}

    try:
        res = await VideosSearch(q, limit=6).next()
        raw_items = res.get("result") or []
    except Exception as exc:
        return 502, {"error": f"Search error: {exc}"}

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


async def _handle_play(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Telegram authentication required."}
    user = auth["user"]
    uid = int(user["id"])

    if uid in BANNED_USERS or await is_banned_user(uid) or await is_gbanned_user(uid):
        return 403, {"error": "You are banned from using this bot."}
    if await is_maintenance() is False and uid != config.OWNER_ID and uid not in SUDOERS:
        return 503, {"error": "Bot is currently in maintenance mode."}

    chat_id = await _parse_target_chat(body.get("chat_id"))
    query = str(body.get("query") or "").strip()
    is_video = bool(body.get("video", False))
    hint_vidid = str(body.get("vidid") or "").strip()
    hint_title = str(body.get("title") or "").strip()
    hint_dur = str(body.get("duration") or "").strip()
    hint_thumb = str(body.get("thumb") or "").strip()

    if not chat_id or chat_id >= 0:
        return 400, {"error": "Valid group chat ID (-100...) is required."}
    if not query or len(query) > 200:
        return 400, {"error": "Provide a song name or YouTube URL."}

    is_member, can_ctrl, _ = await _is_chat_admin(chat_id, uid)
    if not is_member:
        return 403, {"error": "You must be a member of that group to queue music."}

    playtype = await get_playtype(chat_id)
    if playtype != "Everyone" and not can_ctrl:
        return 403, {"error": "Only admins can play music in this group."}

    if _YOUTUBE_ID_RE.match(hint_vidid) and hint_title and hint_dur:
        vidid = hint_vidid
        details = {"title": hint_title, "duration_min": hint_dur, "thumb": hint_thumb}
    else:
        try:
            details, vidid = await YouTube.track(query)
        except Exception as exc:
            return 404, {"error": f"Could not resolve track: {exc}"}

    title = str(details.get("title") or hint_title or "Unknown").title()
    duration_min = details.get("duration_min") or (hint_dur or None)
    if not duration_min:
        return 400, {"error": "Live streams are not supported from the Mini App."}
    if time_to_seconds(duration_min) > config.DURATION_LIMIT:
        return 400, {"error": f"Track exceeds duration limit ({config.DURATION_LIMIT_MIN} min)."}

    try:
        file_path, direct = await YouTube.download(
            vidid, None, video=is_video, videoid=vidid, title=title
        )
    except Exception as exc:
        return 502, {"error": f"Download error: {exc}"}

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
                    text=_["queue_4"].format(pos, title[:27], duration_min, user_mention),
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
        try:
            img = await get_thumb(vidid)
            cap = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_mention,
            )
            run = await app.send_photo(
                chat_id,
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            )
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        except Exception:
            pass
        return 200, {"ok": True, "status": "playing", "title": title}
    except Exception as exc:
        return 400, {"error": str(exc)}


async def _handle_control(headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    auth = _auth_user(headers)
    if not auth:
        return 401, {"error": "Telegram authentication required."}
    uid = int(auth["user"]["id"])
    chat_id = await _parse_target_chat(body.get("chat_id"))
    action = str(body.get("action") or "").strip().lower()

    if not chat_id:
        return 400, {"error": "Invalid chat_id."}
    is_member, can_ctrl, _ = await _is_chat_admin(chat_id, uid)
    if not is_member or not can_ctrl:
        return 403, {"error": "Admin rights required for this voice chat."}
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

        return 400, {"error": "Unsupported action."}
    except Exception as exc:
        return 500, {"error": str(exc)}


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
