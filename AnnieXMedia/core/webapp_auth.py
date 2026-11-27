# Authored By Certified Coders © 2025
import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

import config


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def verify_telegram_init_data(
    init_data: str,
    bot_token: Optional[str] = None,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, Any]]:
    """Verify Telegram Mini App WebApp.initData via official WebAppData HMAC-SHA256."""
    token = bot_token if bot_token is not None else config.BOT_TOKEN
    if not init_data or not token:
        return None

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    except Exception:
        return None

    data_map: Dict[str, str] = {}
    provided_hash = ""
    for k, v in pairs:
        if k == "hash":
            provided_hash = v
        else:
            data_map[k] = v

    if not provided_hash:
        return None

    check_string = "\n".join(f"{k}={data_map[k]}" for k in sorted(data_map))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, provided_hash):
        return None

    try:
        auth_date = int(data_map.get("auth_date", "0"))
    except ValueError:
        return None
    now = int(time.time())
    if auth_date <= 0 or (now - auth_date) > max_age_seconds or (auth_date - now) > 300:
        return None

    user_raw = data_map.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except Exception:
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": data_map.get("query_id"),
        "chat_type": data_map.get("chat_type"),
        "start_param": data_map.get("start_param"),
    }


def _launch_secret(token: str) -> bytes:
    return hmac.new(b"AnnieXGameLaunch", token.encode("utf-8"), hashlib.sha256).digest()


def sign_game_launch(
    payload: Dict[str, Any],
    bot_token: Optional[str] = None,
    ttl_seconds: int = 7200,
) -> str:
    """Create a short-lived HMAC-signed launch token for BotFather game callbacks."""
    token = bot_token if bot_token is not None else config.BOT_TOKEN
    if not token:
        return ""
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_launch_secret(token), raw, hashlib.sha256).digest()
    return f"{_b64url_encode(raw)}.{_b64url_encode(sig)}"


def verify_game_launch(
    launch_token: str,
    bot_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Verify and decode a BotFather game callback launch token."""
    token = bot_token if bot_token is not None else config.BOT_TOKEN
    if not launch_token or not token or "." not in launch_token:
        return None
    try:
        raw_b64, sig_b64 = launch_token.split(".", 1)
        raw = _b64url_decode(raw_b64)
        provided_sig = _b64url_decode(sig_b64)
        expected_sig = hmac.new(_launch_secret(token), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        exp = int(payload.get("exp") or 0)
        if exp < int(time.time()):
            return None
        if not isinstance(payload.get("user_id"), int):
            return None
        return payload
    except Exception:
        return None
