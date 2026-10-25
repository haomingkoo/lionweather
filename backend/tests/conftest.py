import os
import socket

import pytest

LIVE = os.getenv("LIONWEATHER_LIVE_TESTS") == "1"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls real external APIs; runs only with LIONWEATHER_LIVE_TESTS=1")


def pytest_collection_modifyitems(config, items):
    if LIVE:
        return
    skip_live = pytest.mark.skip(reason="needs network; set LIONWEATHER_LIVE_TESTS=1")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Fail any outbound connection unless LIONWEATHER_LIVE_TESTS=1."""
    if LIVE:
        return
    real_connect = socket.socket.connect

    def guarded_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError(f"Network access in tests is blocked: {address}")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
