"""Shared test helpers."""

import pytest
import requests


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


@pytest.fixture
def fake_get(monkeypatch):
    """Serve a local page instead of the network, recording the URLs asked for."""

    def install(html):
        calls = []

        def fake(url, timeout=None):
            calls.append(url)
            return FakeResponse(html)

        monkeypatch.setattr(requests, "get", fake)
        return calls

    return install
