"""Shared security boundary for IDKMesh local browser interfaces."""

from __future__ import annotations

import secrets
from http.server import BaseHTTPRequestHandler

HOST = "127.0.0.1"
MAX_BODY_BYTES = 2 * 1024 * 1024
TOKEN_HEADER = "X-IDKMesh-UI-Token"


def new_session_token() -> str:
    """Return an unguessable token scoped to one local UI process."""
    return secrets.token_urlsafe(24)


def is_loopback_host(host_header: str | None) -> bool:
    """Accept only the loopback host names used by IDKMesh local UIs."""
    if not host_header or any(ch in host_header for ch in "/\\@,\r\n\t "):
        return False
    host = host_header.lower()
    if host.startswith("[") or host.count(":") > 1:
        return False
    hostname, separator, port = host.partition(":")
    if hostname not in {HOST, "localhost"}:
        return False
    return not separator or (port.isascii() and port.isdecimal() and 0 < int(port) <= 65535)


def send_security_headers(handler: BaseHTTPRequestHandler) -> None:
    """Emit the common browser isolation headers for local UI responses."""
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Cross-Origin-Resource-Policy", "same-origin")
    handler.send_header("Cross-Origin-Opener-Policy", "same-origin")
    handler.send_header(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()",
    )
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'none'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; connect-src 'self'; "
        "img-src 'self' data: blob:; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'",
    )
