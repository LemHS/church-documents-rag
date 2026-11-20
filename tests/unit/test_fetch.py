"""Unit tests for the shared retry policy."""

import requests
import pytest

from document_lakehouse.ingestion import fetch


class Response:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []
    monkeypatch.setattr(fetch.time, "sleep", recorded.append)
    return recorded


def sequence(*responses):
    """A `send` that hands back the given responses, then repeats the last one."""
    remaining = list(responses)

    def send():
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return send


def test_returns_the_first_good_response(sleeps):
    calls = []

    def send():
        calls.append(1)
        return Response()

    assert fetch.call(send, "https://example.test/x").text == "ok"
    assert len(calls) == 1
    assert sleeps == []


def test_server_errors_are_retried_with_doubling_backoff(sleeps):
    calls = []

    def send():
        calls.append(1)
        return Response(500 if len(calls) < 3 else 200)

    response = fetch.call(send, "https://example.test/x")

    assert response.status_code == 200
    assert len(calls) == 3
    assert sleeps == [fetch.BACKOFF, fetch.BACKOFF * 2]


def test_giving_up_names_the_url_and_the_attempt_count(sleeps):
    calls = []

    def send():
        calls.append(1)
        return Response(503)

    with pytest.raises(fetch.RetryError) as caught:
        fetch.call(send, "https://example.test/x")

    assert len(calls) == fetch.ATTEMPTS
    assert "https://example.test/x" in str(caught.value)
    assert f"{fetch.ATTEMPTS} attempts" in str(caught.value)
    assert isinstance(caught.value.__cause__, requests.HTTPError)
    assert sleeps == [fetch.BACKOFF, fetch.BACKOFF * 2]


def test_client_errors_are_not_retried(sleeps):
    calls = []

    def send():
        calls.append(1)
        return Response(404)

    with pytest.raises(fetch.RetryError) as caught:
        fetch.call(send, "https://example.test/missing")

    assert len(calls) == 1
    assert sleeps == []
    assert "1 attempt" in str(caught.value)


def test_transport_errors_are_retried(sleeps):
    calls = []

    def send():
        calls.append(1)
        if len(calls) < 3:
            raise requests.ConnectionError("dns")
        return Response()

    assert fetch.call(send, "https://example.test/x").status_code == 200
    assert len(calls) == 3


def test_ordinary_exceptions_are_not_swallowed(sleeps):
    def send():
        raise ValueError("bug in the caller")

    with pytest.raises(ValueError, match="bug in the caller"):
        fetch.call(send, "https://example.test/x")
    assert sleeps == []
