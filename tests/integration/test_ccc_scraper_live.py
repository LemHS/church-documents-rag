"""Live checks against the two archives. Opt in with `pytest -m integration`.

Read-only. Assertions are bounded to invariants the notebook witnessed, since
the sites gain and lose paragraphs over time.
"""

import re

import pandas as pd
import pytest

from document_lakehouse.ingestion.ccc.scraper import (
    get_ccc,
    get_ccc_hierarchy,
    get_ccc_index,
    get_ccc_number_range,
)

pytestmark = pytest.mark.integration


def test_index_is_still_a_list_of_linked_entries():
    url, contents, hrefs, linked = get_ccc_index()

    assert url == "https://www.vatican.va/archive/ENG0015/_INDEX.HTM"
    assert len(contents) == len(hrefs) == len(linked)
    assert len(contents) > 300  # 395 rows when the notebook ran it
    assert contents[0] == "PROLOGUE"
    assert hrefs[0] == "__P1.HTM"
    assert all(href.endswith(".HTM") for href in hrefs if href)


def test_hierarchy_labels_keep_one_row_per_entry():
    _, contents, hrefs, linked = get_ccc_index()

    hierarchy = get_ccc_hierarchy(contents, hrefs, linked)

    assert all(len(values) == len(contents) for values in hierarchy.values())
    assert hierarchy["part"][0] == "PROLOGUE"
    assert hierarchy["roman_numeral"][1] == "I. The life of man - to know and love God"


def test_paragraph_one_still_returns_its_text():
    url, content, hrefs, linked = get_ccc(1)

    assert url == "https://canonlaw.ninja/?v=ccc&nums=1"
    assert content.startswith("God, infinitely perfect and blessed in himself")
    assert isinstance(hrefs, list) and isinstance(linked, list)


def test_number_range_follows_one_real_page():
    _, _, hrefs, _ = get_ccc_index()
    first = next(href for href in hrefs if href)

    result = get_ccc_number_range(pd.DataFrame({"hrefs": [first]}), 0)
    count = result["number_count"].iloc[0]

    assert count == "" or re.fullmatch(r"\d+-\d+", count)
