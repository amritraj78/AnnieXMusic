# Authored By Certified Coders © 2025
import asyncio
import os
import time

try:
    from AnnieXMedia.logging import LOGGER
    log = LOGGER("AnnieXMedia.Server")
except Exception:
    import logging
    log = logging.getLogger("AnnieXMedia.Server")

_start_time = time.time()
_server = None


async def _handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.LimitOverrunError):
            return
        if not line:
            return

        request_line = line.decode("utf-8", errors="ignore").strip()
        parts = request_line.split()
        method = parts[0].upper() if parts else "GET"
        path = parts[1].split("?", 1)[0] if len(parts) > 1 else "/"

        # Read remaining headers with Slowloris & unbounded loop guards
        for _ in range(64):
            try:
                header = await asyncio.wait_for(reader.readline(), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.LimitOverrunError):
                return
            if not header or header in (b"\r\n", b"\n", b""):
                break

        uptime = int(time.time() - _start_time)

        if path in ("/health", "/ping", "/status"):
            body = (
                f'{{"status":"ok","service":"AnnieXMusic","uptime":"{uptime}s"}}\n'
            ).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'><title>AnnieXMusic</title>"
                "<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;"
                "display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}"
                ".card{background:#161b22;padding:2.5rem;border-radius:12px;border:1px solid #30363d;"
                "text-align:center;max-width:420px;box-shadow:0 8px 24px rgba(0,0,0,0.4);}"
                "h1{color:#58a6ff;margin-bottom:0.5rem;font-size:1.6rem;}"
                ".badge{display:inline-block;background:#238636;color:#fff;padding:4px 12px;border-radius:20px;font-size:0.85rem;margin-bottom:1rem;}"
                "p{margin:0.5rem 0;color:#8b949e;}"
                "</style></head><body><div class='card'>"
                "<h1>AnnieXMusic Bot</h1>"
                "<div class='badge'>Running &amp; Healthy</div>"
                f"<p>Instance Uptime: <strong>{uptime}s</strong></p>"
                "<p>Koyeb Deploy Status: <strong>Ready</strong></p>"
                "</div></body></html>\n"
            )
            body = html.encode("utf-8")
            content_type = "text/html; charset=utf-8"

        headers = (
            b"HTTP/1.1 200 OK\r\n"
            + f"Content-Type: {content_type}\r\n".encode("utf-8")
            + b"X-Content-Type-Options: nosniff\r\n"
            + b"Cache-Control: no-store\r\n"
            + b"Connection: close\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        )

        writer.write(headers if method == "HEAD" else headers + body)
        await writer.drain()
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
