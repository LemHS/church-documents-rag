"""Live check for the bible pipeline, bounded to one chapter."""

import pytest

import document_lakehouse.ingestion.bible.pipeline as bible_pipeline

pytestmark = pytest.mark.integration


def test_one_chapter_comes_through_the_pipeline(monkeypatch):
    # the booklist is trimmed to one book so the live run is a single chapter request
    monkeypatch.setattr(bible_pipeline, "get_bible_book", lambda slug: (["Genesis"], ["1"]))

    df = bible_pipeline.scrape_bible()

    assert df["verse"].tolist() == list(range(1, 32))
    assert "In the beginning God created" in df["content"].iloc[0]
    assert df["hrefs"].iloc[0].startswith("#fen-RSVCE")
