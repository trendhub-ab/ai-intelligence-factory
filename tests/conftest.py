from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

import pytest


def _is_loopback_host(host: object) -> bool:
    text = str(host or "").strip().lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def _is_loopback_proxy_endpoint(address: object) -> bool:
    """A local HTTP proxy is an external-network route, not a test server."""
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    host, port = address[:2]
    if not _is_loopback_host(host):
        return False
    for key, value in os.environ.items():
        if key.lower() not in {"http_proxy", "https_proxy", "all_proxy"} or not value:
            continue
        try:
            parsed = urlsplit(value if "://" in value else f"http://{value}")
            proxy_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            continue
        if _is_loopback_host(parsed.hostname) and port == proxy_port:
            return True
    return False


@pytest.fixture(autouse=True)
def block_unexpected_external_network(monkeypatch):
    """Fail fast if deterministic pytest accidentally reaches the public network.

    Loopback stays available for tests that intentionally use a local socket.
    Provider/GitHub/Notion traffic must be mocked at the application boundary.
    """

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if _is_loopback_host(host) and not _is_loopback_proxy_endpoint(address):
            return original_connect(sock, address)
        raise AssertionError(f"Unexpected external network access during pytest: {address!r}")

    def guarded_connect_ex(sock, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if _is_loopback_host(host) and not _is_loopback_proxy_endpoint(address):
            return original_connect_ex(sock, address)
        raise AssertionError(f"Unexpected external network access during pytest: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
