# Authored By Certified Coders © 2025
"""Shared security, SSRF validation, filename sanitization, and secret-redaction helpers."""
import asyncio
import ipaddress
import os
import re
import socket
from pathlib import Path
from typing import Iterable, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import httpx

_BAD_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",
        "100.100.100.200",
    }
)
_EXT_RE = re.compile(r"^[a-zA-Z0-9]{1,8}$")
_SAFE_TOKEN_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_GITHUB_IDENT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_SECRET_PATTERNS = (
    re.compile(r"(mongodb(?:\+srv)?://[^:\s]+:)([^@\s]+)(@)", re.I),
    re.compile(r"(https?://[^:\s/]+:)([^@\s]+)(@)", re.I),
    re.compile(r"\b(\d{8,12}:[A-Za-z0-9_-]{30,50})\b"),
    re.compile(r"([?&](?:api|api_key|token|access_key|key|secret)=)([^&\s]+)", re.I),
)


def _is_ip_restricted(ip_obj: ipaddress._BaseAddress) -> bool:
    """Return True if an IP address is private, loopback, link-local, CGNAT, or non-global."""
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped
    return (
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def _resolve_safe_host(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate HTTP(S) URL syntax and ensure DNS resolves strictly to public global IPs."""
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False, None, None

    if parsed.scheme not in ("http", "https"):
        return False, None, None
    host = parsed.hostname
    if not host:
        return False, None, None
    low_host = host.lower().rstrip(".")
    if low_host in _BAD_HOSTNAMES or low_host.endswith(".local") or low_host.endswith(".internal"):
        return False, None, None

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception:
        return False, None, None
    if not infos:
        return False, None, None

    first_ip: Optional[str] = None
    for _, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0].split("%", 1)[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, None, None
        if _is_ip_restricted(ip_obj):
            return False, None, None
        if first_ip is None:
            first_ip = ip_str

    return True, host, first_ip


async def is_safe_http_url(url: str) -> bool:
    """Async check ensuring url uses HTTP(S) and resolves only to non-restricted global IPs."""
    ok, _, _ = await asyncio.to_thread(_resolve_safe_host, url)
    return ok


async def resolve_safe_target(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Return (is_safe, hostname, resolved_ip) asynchronously."""
    return await asyncio.to_thread(_resolve_safe_host, url)


async def fetch_url_limited(
    url: str,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    max_redirects: int = 5,
    timeout: float = 15.0,
    headers: Optional[dict] = None,
    head_only_redirects: bool = False,
) -> Tuple[bool, int, str, bytes]:
    """
    Safely fetch URL with DNS-checked IP pinning, proxy bypass, redirect hop checks,
    and hard streaming byte limit so responses cannot OOM-crash small containers.
    Returns (ok, status_or_0, final_url_or_err, body_bytes).
    """
    current_url = (url or "").strip()
    req_headers = dict(headers or {})
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as client:
        for _ in range(max_redirects + 1):
            ok, host, pinned_ip = await resolve_safe_target(current_url)
            if not ok or not host or not pinned_ip:
                return False, 0, "Invalid or restricted URL (private/internal address blocked).", b""

            # Pin HTTP connection IP directly for HTTP to neutralize DNS rebinding TOCTOU;
            # HTTPS keeps SNI hostname while closing immediately on redirect.
            parsed = urlparse(current_url)
            target_url = current_url
            hop_headers = dict(req_headers)
            if parsed.scheme == "http":
                ip_host = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
                port_part = f":{parsed.port}" if parsed.port else ""
                netloc = f"{ip_host}{port_part}"
                target_url = parsed._replace(netloc=netloc).geturl()
                hop_headers["Host"] = parsed.netloc

            try:
                method = "HEAD" if head_only_redirects else "GET"
                async with client.stream(method, target_url, headers=hop_headers) as resp:
                    if resp.is_redirect and "location" in resp.headers:
                        current_url = urljoin(current_url, resp.headers["location"])
                        continue
                    if head_only_redirects:
                        return True, resp.status_code, current_url, b""

                    chunks = []
                    total = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            return False, resp.status_code, f"Response exceeds {max_bytes // (1024 * 1024)} MB safety limit.", b""
                        chunks.append(chunk)
                    return True, resp.status_code, current_url, b"".join(chunks)
            except Exception as exc:
                return False, 0, f"Request failed: {exc}", b""

    return False, 0, "Too many redirects.", b""


def sanitize_ext(
    raw_name: Optional[str],
    allowed: Optional[Iterable[str]] = None,
    default: str = "bin",
) -> str:
    """Extract a safe alphanumeric extension with no path separators or dots."""
    ext = default
    if raw_name and "." in raw_name:
        cand = raw_name.rsplit(".", 1)[-1].strip().lower()
        if _EXT_RE.match(cand):
            ext = cand
    if allowed is not None:
        allowed_set = {a.lower().lstrip(".") for a in allowed}
        if ext not in allowed_set:
            return default
    return ext


def safe_path_under(base_dir: str | Path, filename: str) -> Optional[Path]:
    """Resolve a single filename strictly inside base_dir, rejecting traversal."""
    raw = (filename or "").strip()
    if not raw or "\x00" in raw or "/" in raw or "\\" in raw or raw in (".", ".."):
        return None
    root = Path(base_dir).resolve()
    target = (root / raw).resolve()
    if target.parent != root:
        return None
    return target


def sanitize_id_token(token: Optional[str], default: str = "") -> str:
    """Keep only safe ASCII ID characters [A-Za-z0-9_-] for cache paths."""
    s = (token or "").strip()
    return s if _SAFE_TOKEN_RE.match(s) else default


def validate_github_username(raw: Optional[str]) -> Optional[str]:
    """Validate GitHub username/org identifier against strict GitHub rules."""
    s = (raw or "").strip().lstrip("@")
    if not s or not _GITHUB_IDENT_RE.match(s):
        return None
    return quote(s, safe="")


def redact_secrets(text: str) -> str:
    """Mask connection credentials, bot tokens, and API query keys from logs/tracebacks."""
    out = str(text or "")
    for pat in _SECRET_PATTERNS:
        if pat.groups >= 3:
            out = pat.sub(r"\1***\3", out)
        elif pat.groups == 2:
            out = pat.sub(r"\1***", out)
        else:
            out = pat.sub("[REDACTED_TOKEN]", out)
    return out
