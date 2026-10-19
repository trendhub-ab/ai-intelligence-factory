"""Regression coverage for the deterministic test suite's egress boundary."""

from __future__ import annotations

import socket

import pytest


@pytest.mark.parametrize("proxy_variable", ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"))
@pytest.mark.parametrize("connect_method", ("connect", "connect_ex"))
def test_loopback_http_proxy_cannot_escape_network_guard(monkeypatch, proxy_variable, connect_method):
    """A loopback proxy must not tunnel an unmocked external HTTP request."""
    proxy_port = 59671
    monkeypatch.setenv(proxy_variable, f"http://127.0.0.1:{proxy_port}")

    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="Unexpected external network access during pytest"):
            getattr(sock, connect_method)(("127.0.0.1", proxy_port))


def test_unrelated_loopback_tcp_is_still_available_for_local_http_tests():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with socket.socket() as client:
            client.connect(listener.getsockname())
            connection, _ = listener.accept()
            connection.close()
