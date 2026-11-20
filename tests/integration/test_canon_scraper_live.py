"""Live checks for the canon scraper. Opt in with `pytest -m integration`.

Read-only. Assertions stay on the invariants the notebook witnessed.
"""

import pytest

from document_lakehouse.ingestion.canon.scraper import get_canon, metadata_to_nested

pytestmark = pytest.mark.integration


def test_canon_350_still_has_its_breadcrumb():
    url, content, hrefs, linked, metadata = get_canon(350)

    assert url == "https://canonlaw.ninja/?nums=350"
    assert metadata[0] == "The People of God"
    assert metadata[-1] == "The Cardinals of the Holy Roman Church"
    assert len(metadata) == 4  # the depth the notebook recorded
    assert len(content) > 100


def test_canon_past_the_end_answers_with_an_alert():
    _, content, hrefs, linked, metadata = get_canon(9999)

    assert content == "No results found."
    assert hrefs == [] and linked == []
    assert metadata == []


def test_live_breadcrumb_nests_one_level_per_label():
    _, _, _, _, metadata = get_canon(350)

    nested = metadata_to_nested(metadata)

    depth = 0
    while nested:
        (only,) = nested.keys()
        nested = nested[only]
        depth += 1

    assert depth == len(metadata)
