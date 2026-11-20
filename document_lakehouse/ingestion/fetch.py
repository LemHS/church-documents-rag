"""One retry policy for every scraper in this package.

Every network call goes through `call`, which retries a bounded number of
times with a short backoff and then raises `RetryError` naming the URL and the
attempt count — so a caller can tell "still working" from "gave up".
"""

import time

import requests

ATTEMPTS = 3
BACKOFF = 0.5

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryError(RuntimeError):
    """Every attempt at one URL failed."""


def _worth_retrying(exc):
    """Retry server and transport failures; a 404 or a 403 will not heal."""
    if isinstance(exc, requests.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return status in RETRY_STATUS
    return isinstance(exc, requests.RequestException)


def call(send, url, attempts=ATTEMPTS, backoff=BACKOFF):
    """Run `send()` — one HTTP call — until it answers, or give up.

    Returns the response with its status already checked.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            response = send()
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            if attempt == attempts or not _worth_retrying(exc):
                break
            time.sleep(backoff * 2 ** (attempt - 1))

    plural = "attempt" if attempt == 1 else "attempts"
    raise RetryError(f"{url} failed after {attempt} {plural}: {last}") from last
