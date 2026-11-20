"""Unit tests for the CCC scrapers, pinned to what the notebook produced.

`fixtures/ccc_index.html` is the vatican.va index page as fetched when the
pipeline ran; `fixtures/ccc_index_expected.csv` is the output the notebook
wrote from that run (395 rows, 2026-11-10). The expectations below come from
that pair, not from reading the code.
"""

import csv
from pathlib import Path

import pandas as pd
import pytest
import requests

from document_lakehouse.ingestion import fetch
from document_lakehouse.ingestion.ccc.scraper import (
    get_ccc,
    get_ccc_hierarchy,
    get_ccc_index,
    get_ccc_number_range,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HIERARCHY_COLUMNS = [
    "part",
    "section",
    "chapter",
    "article",
    "roman_numeral",
    "content",
    "hrefs",
    "linked_content",
]


@pytest.fixture
def expected_rows():
    with open(FIXTURES / "ccc_index_expected.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_index_reproduces_the_recorded_output(expected_rows, fake_get):
    calls = fake_get((FIXTURES / "ccc_index.html").read_text(encoding="utf-8"))

    url, contents, hrefs, linked = get_ccc_index()

    assert url == "https://www.vatican.va/archive/ENG0015/_INDEX.HTM"
    assert calls == [url]
    assert contents == [row["content"] for row in expected_rows]
    assert hrefs == [row["hrefs"] for row in expected_rows]
    assert linked == [row["linked_content"] for row in expected_rows]


def test_hierarchy_columns_match_the_recorded_output(expected_rows):
    contents = [row["content"] for row in expected_rows]
    hrefs = [row["hrefs"] for row in expected_rows]
    linked = [row["linked_content"] for row in expected_rows]

    hierarchy = get_ccc_hierarchy(contents, hrefs, linked)

    assert list(hierarchy) == HIERARCHY_COLUMNS
    for column in HIERARCHY_COLUMNS:
        assert hierarchy[column] == [row[column] for row in expected_rows]


def test_number_range_reads_the_numbering_from_a_recorded_page(fake_get):
    calls = fake_get((FIXTURES / "ccc_page_p2.html").read_text(encoding="utf-8"))

    result = get_ccc_number_range(pd.DataFrame({"hrefs": ["__P2.HTM"]}), 0)

    # the notebook recorded ['1', '2', '3'] for this page; the function now
    # reports the same numbers as a range
    assert result["number_count"].tolist() == ["1-3"]
    assert calls == ["https://www.vatican.va/archive/ENG0015/__P2.HTM"]


def test_number_range_leaves_rows_without_a_page_empty(fake_get):
    calls = fake_get("<html></html>")

    result = get_ccc_number_range(pd.DataFrame({"hrefs": ["", ""]}), 0)

    assert result["number_count"].tolist() == ["", ""]
    assert calls == []


def test_paragraph_returns_the_text_after_its_label(fake_get):
    calls = fake_get((FIXTURES / "ccc_paragraph.html").read_text(encoding="utf-8"))

    url, content, hrefs, linked = get_ccc(1)

    assert url == "https://canonlaw.ninja/?v=ccc&nums=1"
    assert calls == [url]
    # the leading "Paragraph 1." label is the first child and is skipped
    assert content.startswith("God, infinitely perfect and blessed in himself")
    assert hrefs == []
    assert linked == []


@pytest.mark.xfail(
    strict=True,
    reason="CONCERN.md: get_ccc raises on paragraphs past the end of the Code",
)
def test_paragraph_past_the_end_returns_no_results(fake_get):
    fake_get((FIXTURES / "canonlaw_no_results.html").read_text(encoding="utf-8"))

    _, content, _, _ = get_ccc(9999)

    assert "No results" in content


def test_number_range_keeps_what_came_back_when_it_gives_up(monkeypatch):
    monkeypatch.setattr("document_lakehouse.ingestion.fetch.time.sleep", lambda _: None)
    calls = []

    class ServerError:
        status_code = 500

    def failing(url, timeout=None):
        calls.append(url)
        if "P2" in url:
            raise requests.HTTPError("500", response=ServerError())

        class Page:
            text = '<div class="MsoNormal">1 text</div>'

            def raise_for_status(self):
                pass

        return Page()

    monkeypatch.setattr(requests, "get", failing)
    frame = pd.DataFrame({"hrefs": ["__P1.HTM", "__P2.HTM"]})

    with pytest.raises(fetch.RetryError, match="__P2.HTM"):
        get_ccc_number_range(frame, 0)

    # the row that answered keeps its range, the row that never ran stays empty
    assert frame["number_count"].tolist()[0] == "1-1"
    assert frame["number_count"].isna().tolist() == [False, True]
    assert len(calls) == 1 + fetch.ATTEMPTS
