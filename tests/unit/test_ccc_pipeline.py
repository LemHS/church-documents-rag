"""Unit tests for the CCC pipeline: index -> hierarchy table -> ranges."""

import csv
from pathlib import Path

import pytest

import document_lakehouse.ingestion.ccc.pipeline as ccc_pipeline

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

RECORDED_COLUMNS = [
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
def recorded():
    """The notebook's recorded output, one dict per index row."""
    with (FIXTURES / "ccc_index_expected.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def index_page(fake_get):
    return fake_get((FIXTURES / "ccc_index.html").read_text(encoding="utf-8"))


@pytest.fixture
def page_fetch_seen(monkeypatch):
    """Stand in for the 395 page fetches, recording what the pipeline handed over."""
    seen = {}

    def fake_number_range(df, start):
        seen["df"] = df.copy()
        seen["start"] = start
        out = df.copy()
        out["number_count"] = ""
        return out

    monkeypatch.setattr(ccc_pipeline, "get_ccc_number_range", fake_number_range)
    return seen


def test_pipeline_wires_index_and_hierarchy_into_one_table(index_page, page_fetch_seen, recorded):
    df = ccc_pipeline.build_ccc_hierarchy()

    assert len(df) == 395 == len(recorded)
    assert list(df.columns)[: len(RECORDED_COLUMNS)] == RECORDED_COLUMNS
    assert df["number_count"].tolist() == [""] * 395

    # the same rows the notebook recorded, through the same scrapers
    for row in (0, 1, 17, 394):
        assert df["content"].iloc[row] == recorded[row]["content"]
        assert df["hrefs"].iloc[row] == recorded[row]["hrefs"]
        assert df["linked_content"].iloc[row] == recorded[row]["linked_content"]

    assert page_fetch_seen["start"] == 0
    assert index_page  # the index page was actually requested


def test_limit_trims_the_index_before_the_pages_are_fetched(index_page, page_fetch_seen):
    df = ccc_pipeline.build_ccc_hierarchy(limit=3)

    assert len(df) == 3
    assert len(page_fetch_seen["df"]) == 3
    assert list(df.columns)[: len(RECORDED_COLUMNS)] == RECORDED_COLUMNS


def test_start_is_passed_through_to_the_range_scraper(index_page, page_fetch_seen):
    ccc_pipeline.build_ccc_hierarchy(start=7, limit=1)

    assert page_fetch_seen["start"] == 7
