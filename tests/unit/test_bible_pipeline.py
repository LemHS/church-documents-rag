"""Unit tests for the bible pipeline driver loop."""

import csv
import logging
from pathlib import Path

import pytest

import document_lakehouse.ingestion.bible.pipeline as bible_pipeline

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def make_get_bible_chapter(failing=(), repeating=False):
    calls = []

    def get_bible_chapter(translation, book, chapter, tries=0):
        calls.append((translation, book, chapter))
        if (book, chapter) in failing:
            raise RuntimeError(f"{book} {chapter} is down")

        # `repeating` answers every chapter with the same rows, so the
        # pipeline's drop_duplicates has something to collapse
        chapter_rows = 1 if repeating else chapter
        content = ["same text", "more text"] if repeating else [f"{book} {chapter}:1", f"{book} {chapter}:2"]
        return (
            [f"url-{book}-{chapter_rows}"] * 2,
            [book] * 2,
            [chapter_rows] * 2,
            [1, 2],
            content,
            ["a;b", ""],
            ["first", ""],
        )

    get_bible_chapter.calls = calls
    return get_bible_chapter


def install(monkeypatch, books, chapters, chapter_fake):
    monkeypatch.setattr(bible_pipeline, "get_bible_book", lambda slug: (books, chapters))
    monkeypatch.setattr(bible_pipeline, "get_bible_chapter", chapter_fake)


def test_each_book_is_walked_once_chapter_by_chapter(monkeypatch):
    fake = make_get_bible_chapter()
    install(monkeypatch, ["Genesis", "Genesis", "Exodus"], ["2", "2", "1"], fake)

    df = bible_pipeline.scrape_bible()

    assert fake.calls == [("RSVCE", "Genesis", 1), ("RSVCE", "Genesis", 2), ("RSVCE", "Exodus", 1)]
    assert df.attrs["failures"] == []
    assert list(df.columns) == ["book", "chapter", "verse", "url", "content", "linked_content", "hrefs"]
    assert df["chapter"].tolist() == [1, 1, 2, 2, 1, 1]
    assert df.loc[0, "hrefs"] == "a;b"
    assert df.loc[0, "linked_content"] == "first"


def test_a_failed_chapter_is_logged_and_the_run_carries_on(monkeypatch, caplog):
    fake = make_get_bible_chapter(failing=[("Genesis", 2)])
    install(monkeypatch, ["Genesis", "Exodus"], ["2", "1"], fake)

    with caplog.at_level(logging.WARNING, logger="document_lakehouse.ingestion.bible.pipeline"):
        df = bible_pipeline.scrape_bible(max_failures=1)

    assert df["book"].tolist() == ["Genesis", "Genesis", "Exodus", "Exodus"]
    assert "Genesis 2 failed" in caplog.text
    assert fake.calls == [("RSVCE", "Genesis", 1), ("RSVCE", "Genesis", 2), ("RSVCE", "Exodus", 1)]
    # the skipped chapter is on the frame, so the gap is nameable afterwards
    assert df.attrs["failures"] == [
        {"book": "Genesis", "chapter": 2, "reason": "error", "error": "Genesis 2 is down"},
    ]
    assert "1 item(s) could not be fetched: Genesis 2" in caplog.text


def test_giving_up_raises_once_the_budget_is_spent(monkeypatch):
    fake = make_get_bible_chapter(failing=[("Genesis", 1), ("Genesis", 2)])
    install(monkeypatch, ["Genesis"], ["2"], fake)

    with pytest.raises(RuntimeError, match="Genesis 2 is down"):
        bible_pipeline.scrape_bible(max_failures=1)


def test_identical_verses_are_dropped(monkeypatch):
    fake = make_get_bible_chapter(repeating=True)
    install(monkeypatch, ["Genesis"], ["2"], fake)

    df = bible_pipeline.scrape_bible()

    assert len(df) == 2
    assert len(fake.calls) == 2


def test_recorded_genesis_chapter_comes_through_the_pipeline(monkeypatch, fake_get):
    fake_get((FIXTURES / "biblegateway_genesis_1.html").read_text(encoding="utf-8"))
    from document_lakehouse.ingestion.bible.scraper import get_bible_chapter

    monkeypatch.setattr(bible_pipeline, "get_bible_book", lambda slug: (["Genesis"], ["1"]))
    monkeypatch.setattr(bible_pipeline, "get_bible_chapter", get_bible_chapter)

    df = bible_pipeline.scrape_bible()

    with (FIXTURES / "bible_genesis_1_expected.csv").open(encoding="utf-8", newline="") as handle:
        recorded = list(csv.DictReader(handle))

    assert len(df) == 31 == len(recorded)
    for row, expected in enumerate(recorded):
        assert df.loc[row, "verse"] == (int(expected["verse"]) if expected["verse"] else "")
        assert df.loc[row, "content"] == expected["content"]
        assert df.loc[row, "hrefs"] == expected["hrefs"]
        assert df.loc[row, "linked_content"] == expected["linked_content"]
