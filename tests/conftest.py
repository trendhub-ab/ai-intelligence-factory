from __future__ import annotations

import ipaddress
import socket

import pytest


def _is_loopback_host(host: object) -> bool:
    text = str(host or "").strip().lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
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
        if _is_loopback_host(host):
            return original_connect(sock, address)
        raise AssertionError(f"Unexpected external network access during pytest: {address!r}")

    def guarded_connect_ex(sock, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if _is_loopback_host(host):
            return original_connect_ex(sock, address)
        raise AssertionError(f"Unexpected external network access during pytest: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
