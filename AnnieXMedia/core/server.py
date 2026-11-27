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
            uptime = int(time.time() - _start_time)
            body = f'{{"status":"ok","service":"AnnieXMusic","uptime":"{uptime}s"}}\n'.encode("utf-8")
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
                "<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;"
                "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;}"
                ".card{background:#161b22;padding:2.2rem;border-radius:16px;border:1px solid #30363d;"
                "text-align:center;max-width:440px;width:100%;box-shadow:0 8px 24px rgba(0,0,0,0.4);}"
                "h1{color:#58a6ff;margin:0 0 0.6rem;font-size:1.6rem;}"
                ".badge{display:inline-block;background:#238636;color:#fff;padding:4px 12px;border-radius:20px;font-size:0.85rem;margin-bottom:1rem;}"
                "p{margin:0.45rem 0;color:#8b949e;}"
                ".btns{display:flex;gap:10px;justify-content:center;margin-top:1.4rem;flex-wrap:wrap;}"
                ".btn{display:inline-block;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:600;color:#fff;background:#1f6feb;}"
                ".btn.alt{background:#8957e5;}"
                "</style></head><body><div class='card'>"
                "<h1>AnnieXMusic Bot</h1>"
                "<div class='badge'>Running &amp; Healthy</div>"
                f"<p>Instance Uptime: <strong>{uptime}s</strong></p>"
                "<p>Telegram Mini App &amp; Neon Arcade Ready</p>"
                "<div class='btns'>"
                "<a class='btn' href='/app'>🎵 Music Mini App</a>"
                "<a class='btn alt' href='/game'>🎮 Neon Arcade</a>"
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
