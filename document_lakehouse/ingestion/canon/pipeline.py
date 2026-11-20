"""End-to-end canon-law scrape: every canon number until the corpus runs out."""

import logging

import pandas as pd

from ..failures import attach
from .scraper import get_canon

log = logging.getLogger(__name__)


def scrape_canon(max_id=2000, max_failures=5):
    """Scrape canon law numbers 0..max_id, giving up after max_failures misses.

    A number whose page says "No results" counts as a miss, the same as a
    failed request, so a gap in the numbering ends the run rather than
    being skipped over silently. Every miss is recorded in
    `frame.attrs["failures"]` with its number and reason.
    """
    dct = {"id": [],
           "url": [],
           "metadata": [],
           "content": [],
           "linked_content": [],
           "hrefs": []}
    failures = []
    id = 0
    tries = 0

    while (tries <= max_failures) and (id < max_id):
        try:
            url, content, hrefs, linked_content, metadata = get_canon(id)
            if "No results" in content:
                failures.append({"id": id, "reason": "no results", "error": ""})
                tries += 1
                continue

            dct["id"].append(id)
            dct["url"].append(url)
            dct["metadata"].append(" > ".join(metadata))
            dct["content"].append(content)
            dct["linked_content"].append(";".join(linked_content))
            dct["hrefs"].append(";".join(hrefs))
            id += 1
        except Exception as e:
            failures.append({"id": id, "reason": "error", "error": str(e)})
            log.warning("canon %s failed (%s/%s): %s", id, tries + 1, max_failures, e)
            tries += 1
            continue

    return attach(pd.DataFrame(dct), failures, lambda failure: f"canon {failure['id']}")
