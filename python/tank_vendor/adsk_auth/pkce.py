# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""PKCE flow: code pair, auth URL, callback server, code/refresh exchange."""

from __future__ import annotations

import base64
import errno
import hashlib
import logging
import secrets
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict
from urllib.parse import parse_qs, urlencode, urlparse
import json
import urllib.request
import webbrowser

from .config import AuthConfig

_logger = logging.getLogger(__name__)

REST_TIMEOUT = 30


def create_code_pair() -> tuple[str, str]:
    """Create PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(40)
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return (code_challenge, code_verifier)


def build_authorize_url(config: AuthConfig, code_challenge: str) -> tuple[str, str]:
    """Build authorize URL and state; returns (url, state)."""
    state = secrets.token_urlsafe()
    params = {
        "client_id": config.application_id,
        "redirect_uri": config.callback_url,
        "response_type": "code",
        "scope": " ".join(config.required_application_scopes),
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "nonce": secrets.token_urlsafe(),
    }
    url = f"{config.base_url}/authentication/v2/authorize?{urlencode(params)}"
    return (url, state)


def exchange_code(
    config: AuthConfig,
    code: str,
    code_verifier: str,
) -> Dict[str, Any]:
    """Exchange authorization code for tokens."""
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.callback_url,
        "client_id": config.application_id,
        "code_verifier": code_verifier,
    }
    encoded_data = urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        f"{config.base_url}/authentication/v2/token",
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REST_TIMEOUT) as response:
        return json.loads(response.read())


def exchange_refresh_token(config: AuthConfig, refresh_token: str) -> Dict[str, Any]:
    """Exchange refresh token for new access (and optionally refresh) token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config.application_id,
    }
    encoded_data = urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        f"{config.base_url}/authentication/v2/token",
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def _callback_server_port(callback_url: str) -> int:
    parsed = urlparse(callback_url)
    if parsed.port is not None:
        return parsed.port
    return 80 if parsed.scheme == "http" else 443


# Errno for "address family not supported" (IPv6 disabled or unavailable).
# Unix: EAFNOSUPPORT (97); Windows: WSAEAFNOSUPPORT (10047).
_ERRNO_AF_NOT_SUPPORTED = (getattr(errno, "EAFNOSUPPORT", 97), 10047)


def _is_port_in_use(port: int) -> bool:
    """Return True if the port is already bound (IPv4 or IPv6)."""
    port = int(port)
    # Probe IPv4 (e.g. python -m http.server binds here)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", port))
    except OSError as e:
        if getattr(e, "errno", None) in (errno.EADDRINUSE, errno.EACCES):
            return True
        raise
    # Probe IPv6 (dual-stack; same port can be bound separately on some OSes).
    # If IPv6 is not available (EAFNOSUPPORT etc.), skip probe and assume port is free for our use.
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            if hasattr(socket, "IPV6_V6ONLY"):
                s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            s.bind(("::", port))
    except OSError as e:
        err = getattr(e, "errno", None)
        if err in (errno.EADDRINUSE, errno.EACCES):
            return True
        if err in _ERRNO_AF_NOT_SUPPORTED:
            _logger.debug("IPv6 not available, skipping IPv6 port probe")
            return False
        raise
    return False


# Simple page with button (no immediate window.close) so callback is fully
# processed before the window closes.
_CALLBACK_HTML = b"""<!DOCTYPE html><html><body>
    <p>Authentication successful. You can close this window.</p>
    <button type="button" onclick="window.open('', '_self', ''); window.close();">
        You can close this window
    </button>
</body></html>"""


class _CallbackHandler(BaseHTTPRequestHandler):
    """Capture OAuth callback ?code=...&state=... from the local HTTP server."""

    session_store: Dict[str, Any] = {}

    def do_GET(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        if "error" in q:
            msg = q.get("error_description", q.get("error", [b"Unknown error"]))
            _logger.error("OAuth callback error: %s", msg[0] if msg else "unknown")
        elif "code" in q and "state" in q:
            self.session_store[q["state"][0]] = q["code"][0]
            _logger.info("Received OAuth callback with code and state")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(_CALLBACK_HTML)
        # Do NOT call server.shutdown() here: with ThreadingMixIn the handler runs
        # in a worker thread; the main server thread is blocked in accept(). Rely
        # on the main thread polling session_store and timing out instead.

    def log_message(self, format: str, *args: Any) -> None:
        _logger.debug("%s", args)


class _ThreadingCallbackServerDualStack(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server binding to :: with IPV6_V6ONLY=0 (dual-stack)."""

    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        self.socket = socket.socket(self.address_family, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "IPV6_V6ONLY"):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        self.socket.bind(("::", self.server_address[1]))
        self.server_address = self.socket.getsockname()


class _ThreadingCallbackServerIPv4(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server binding to 0.0.0.0 (IPv4 only). Fallback when IPv6 is unavailable."""

    def server_bind(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()


def run_callback_server(
    session_store: Dict[str, Any],
    port: int,
    ready_event: threading.Event | None = None,
    init_error: list[BaseException] | None = None,
) -> None:
    """Run HTTP server in current thread to capture ?code=...&state=... ."""
    _CallbackHandler.session_store = session_store
    port = int(port)
    try:
        server = _ThreadingCallbackServerDualStack(("::", port), _CallbackHandler)
    except OSError as e:
        err = getattr(e, "errno", None)
        if err in (errno.EADDRINUSE, errno.EACCES):
            if init_error is not None:
                init_error.append(e)
            if ready_event is not None:
                ready_event.set()
            return
        if err in _ERRNO_AF_NOT_SUPPORTED:
            _logger.debug("IPv6 not available, using IPv4 callback server")
            server = _ThreadingCallbackServerIPv4(("0.0.0.0", port), _CallbackHandler)
        else:
            raise
    # Request handler threads must be daemon so the process exits after we have the code.
    server.daemon_threads = True
    if ready_event is not None:
        ready_event.set()
    server.serve_forever()


def web_authenticate(
    config: AuthConfig,
    *,
    time_out: float = 30.0,
    browser: Any = None,
) -> Dict[str, Any]:
    """Run PKCE in browser; return token dict (access_token, refresh_token, ...)."""
    import time

    code_challenge, code_verifier = create_code_pair()
    auth_url, state = build_authorize_url(config, code_challenge)
    session_store: Dict[str, Any] = {state: None}
    port = _callback_server_port(config.callback_url)
    if _is_port_in_use(port):
        raise RuntimeError(
            f"Port {port} is already in use (callback URL {config.callback_url}). "
            "Another auth process may be running. Exit it or use a different callback URL."
        )
    ready_event = threading.Event()
    init_error: list[BaseException] = []

    server_thread = threading.Thread(
        target=run_callback_server,
        args=(session_store, port),
        kwargs={"ready_event": ready_event, "init_error": init_error},
    )
    server_thread.daemon = True
    server_thread.start()
    # Ensure server is bound and listening before opening browser (avoids race on Windows)
    if not ready_event.wait(timeout=5):
        _logger.warning("Callback server may not be ready yet")
    if init_error:
        e = init_error[0]
        raise RuntimeError(
            f"Port {port} is already in use (callback URL {config.callback_url}). "
            "Another auth process may be running. Exit it or use a different callback URL."
        ) from e
    time.sleep(0.5)
    try:
        b = webbrowser.get(using=browser)
        b.open_new(auth_url)
        # With ThreadingMixIn the server thread never exits; poll with short joins
        # so we return as soon as the callback handler has set session_store[state].
        deadline = time.monotonic() + time_out
        while time.monotonic() < deadline:
            if session_store.get(state) is not None:
                break
            server_thread.join(timeout=0.25)
    except webbrowser.Error as e:
        _logger.error("Browser error: %s", e)
        server_thread.join(timeout=0.5)

    if session_store.get(state) is None:
        raise RuntimeError("Failed to obtain authorization code from browser")
    code = session_store[state]
    token = exchange_code(config, code, code_verifier)
    if not token or "access_token" not in token:
        raise RuntimeError("Token exchange did not return an access_token")
    return token
