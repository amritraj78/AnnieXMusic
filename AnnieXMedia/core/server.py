# Authored By Certified Coders © 2025
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from AnnieXMedia.logging import LOGGER
    log = LOGGER("AnnieXMedia.Server")
except Exception:
    import logging
    log = logging.getLogger("AnnieXMedia.Server")

_start_time = time.time()
_server = None
_WEB_DIR = Path(__file__).resolve().parent.parent / "assets" / "web"
_ASSET_CACHE: Dict[str, bytes] = {}
_MAX_BODY_BYTES = 65536

_STATUS_MAP = {
    200: "200 OK",
    400: "400 Bad Request",
    401: "401 Unauthorized",
    403: "403 Forbidden",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    413: "413 Payload Too Large",
    429: "429 Too Many Requests",
    500: "500 Internal Server Error",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
}


def _load_web_asset(filename: str) -> Optional[bytes]:
    cached = _ASSET_CACHE.get(filename)
    if cached is not None:
        return cached
    asset = (_WEB_DIR / filename).resolve()
    if asset.parent != _WEB_DIR.resolve() or not asset.is_file():
        return None
    try:
        data = asset.read_bytes()
        _ASSET_CACHE[filename] = data
        return data
    except OSError:
        return None


async def _load_web_asset_async(filename: str) -> Optional[bytes]:
    cached = _ASSET_CACHE.get(filename)
    if cached is not None:
        return cached
    return await asyncio.to_thread(_load_web_asset, filename)


async def _read_http_request(
    reader: asyncio.StreamReader,
) -> Optional[Tuple[str, str, str, Dict[str, str], bytes]]:
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
    except (asyncio.TimeoutError, asyncio.LimitOverrunError):
        return None
    if not line:
        return None

    parts = line.decode("utf-8", errors="ignore").strip().split()
    if len(parts) < 2:
        return None
    method = parts[0].upper()
    raw_target = parts[1]
    if "?" in raw_target:
        path, query_str = raw_target.split("?", 1)
    else:
        path, query_str = raw_target, ""

    headers: Dict[str, str] = {}
    for _ in range(64):
        try:
            header_line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        except (asyncio.TimeoutError, asyncio.LimitOverrunError):
            return None
        if not header_line or header_line in (b"\r\n", b"\n", b""):
            break
        decoded = header_line.decode("utf-8", errors="ignore").strip()
        if ":" in decoded:
            k, v = decoded.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    body = b""
    if "content-length" in headers:
        try:
            content_len = int(headers["content-length"])
        except ValueError:
            content_len = -1
        if content_len < 0 or content_len > _MAX_BODY_BYTES:
            return method, "__TOO_LARGE__", query_str, headers, b""
        if content_len > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(content_len), timeout=5.0)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                return None

    return method, path, query_str, headers, body


_HTML_CSP = (
    "default-src 'self' https:; "
    "script-src 'self' 'unsafe-inline' https://telegram.org; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https: data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'"
)


def _send_response_bytes(
    status_code: int, content_type: str, body: bytes, method: str = "GET"
) -> bytes:
    status_text = _STATUS_MAP.get(status_code, f"{status_code} OK")
    csp = _HTML_CSP if "text/html" in content_type else "default-src 'none'"
    headers = (
        f"HTTP/1.1 {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        "Referrer-Policy: no-referrer\r\n"
        "Permissions-Policy: camera=(), microphone=(), geolocation=()\r\n"
        f"Content-Security-Policy: {csp}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("utf-8")
    return headers if method == "HEAD" else headers + body


async def _handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        parsed = await _read_http_request(reader)
        if not parsed:
            return
        method, path, query_str, headers, body_bytes = parsed

        if path == "__TOO_LARGE__":
            resp = _send_response_bytes(
                413, "application/json; charset=utf-8", b'{"error":"Payload too large"}\n', method
            )
        elif method not in ("GET", "HEAD", "POST"):
            resp = _send_response_bytes(
                405, "application/json; charset=utf-8", b'{"error":"Method not allowed"}\n', method
            )
        elif path in ("/health", "/ping", "/status"):
            from AnnieXMedia.core.self_heal import get_health_snapshot

            snap = get_health_snapshot()
            payload = {
                "status": "ok",
                "service": "AnnieXMusic",
                "uptime": f"{int(time.time() - _start_time)}s",
                "db_ok": snap["db_ok"],
                "bot_connected": snap["bot_connected"],
                "recoveries": snap["recoveries"],
            }
            body = (json.dumps(payload) + "\n").encode("utf-8")
            resp = _send_response_bytes(200, "application/json; charset=utf-8", body, method)
        elif path == "/app":
            asset = await _load_web_asset_async("app.html")
            if asset is None:
                resp = _send_response_bytes(404, "text/plain; charset=utf-8", b"Mini App not found", method)
            else:
                resp = _send_response_bytes(200, "text/html; charset=utf-8", asset, method)
        elif path == "/game":
            asset = await _load_web_asset_async("game.html")
            if asset is None:
                resp = _send_response_bytes(404, "text/plain; charset=utf-8", b"Game not found", method)
            else:
                resp = _send_response_bytes(200, "text/html; charset=utf-8", asset, method)
        elif path.startswith("/api/"):
            from AnnieXMedia.core.webapp_api import handle_api_request

            code, payload = await handle_api_request(method, path, query_str, headers, body_bytes)
            body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            resp = _send_response_bytes(code, "application/json; charset=utf-8", body, method)
        elif path == "/":
            uptime = int(time.time() - _start_time)
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>AnnieXMusic</title>"
                "<style>"
                "*{box-sizing:border-box}"
                "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
                "background:radial-gradient(circle at 15% 15%,rgba(255,77,148,.20),transparent 46%),"
                "radial-gradient(circle at 85% 20%,rgba(0,245,212,.16),transparent 44%),"
                "radial-gradient(circle at 50% 95%,rgba(255,184,77,.12),transparent 48%),#07060d;"
                "color:#f5f3ff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:18px;}"
                ".card{background:rgba(17,14,28,.86);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);"
                "padding:2.3rem 2rem;border-radius:24px;border:1px solid rgba(255,77,148,.24);"
                "text-align:center;max-width:460px;width:100%;"
                "box-shadow:0 24px 60px rgba(0,0,0,.62),0 0 40px rgba(255,77,148,.12);}"
                "h1{margin:0 0 .65rem;font-size:1.75rem;font-weight:800;letter-spacing:-.02em;"
                "background:linear-gradient(135deg,#ff4d94 0%,#ffb84d 52%,#00f5d4 100%);"
                "-webkit-background-clip:text;background-clip:text;color:transparent;}"
                ".badge{display:inline-flex;align-items:center;gap:6px;background:rgba(0,245,212,.14);"
                "color:#00f5d4;border:1px solid rgba(0,245,212,.35);padding:5px 14px;border-radius:999px;"
                "font-size:.8rem;font-weight:700;margin-bottom:1.1rem;}"
                "p{margin:.42rem 0;color:#b4acd4;font-size:.94rem;}"
                "strong{color:#f5f3ff;}"
                ".btns{display:flex;gap:10px;justify-content:center;margin-top:1.5rem;flex-wrap:wrap;}"
                ".btn{display:inline-block;padding:11px 20px;border-radius:14px;text-decoration:none;"
                "font-weight:700;font-size:.92rem;color:#fff;"
                "background:linear-gradient(135deg,#ff4d94,#ff7a59);"
                "box-shadow:0 8px 24px rgba(255,77,148,.32);transition:transform .15s ease;}"
                ".btn:active{transform:scale(.97);}"
                ".btn.alt{color:#071216;background:linear-gradient(135deg,#00f5d4,#5efce8);"
                "box-shadow:0 8px 24px rgba(0,245,212,.26);}"
                "</style></head><body><div class='card'>"
                "<h1>AnnieXMusic</h1>"
                "<div class='badge'>● Running &amp; Healthy</div>"
                f"<p>Instance Uptime: <strong>{uptime}s</strong></p>"
                "<p>Velvet Aurora Mini App &amp; 6-in-1 Neon Arcade Ready</p>"
                "<div class='btns'>"
                "<a class='btn' href='/app'>🎵 Music Mini App</a>"
                "<a class='btn alt' href='/game'>🕹️ 6-in-1 Arcade</a>"
                "</div></div></body></html>\n"
            ).encode("utf-8")
            resp = _send_response_bytes(200, "text/html; charset=utf-8", html, method)
        else:
            resp = _send_response_bytes(404, "text/plain; charset=utf-8", b"Not Found", method)

        writer.write(resp)
        await asyncio.wait_for(writer.drain(), timeout=5.0)
    except Exception as e:
        log.debug(f"Web server request handling error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def start_web_server(port: int = None):
    global _server
    if _server is not None:
        return _server

    if port is None:
        try:
            port = int(os.environ.get("PORT", "8080"))
        except ValueError:
            port = 8080

    try:
        _server = await asyncio.start_server(
            _handle_request, "0.0.0.0", port, limit=65536, reuse_address=True
        )
        log.info(f"Healthcheck web server running on http://0.0.0.0:{port}")
        return _server
    except Exception as e:
        log.warning(f"Could not bind web server on port {port}: {e}")
        return None


async def stop_web_server():
    global _server
    if _server is not None:
        try:
            _server.close()
            await _server.wait_closed()
            log.info("Healthcheck web server stopped.")
        except Exception as e:
            log.warning(f"Error closing web server: {e}")
        finally:
            _server = None
