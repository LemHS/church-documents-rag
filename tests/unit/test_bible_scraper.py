"""Unit tests for the bible scraper, pinned to the notebook's recorded output.

`fixtures/biblegateway_genesis_1.html` is Genesis 1 as the notebook fetched it,
trimmed to the elements the scraper matches; `fixtures/bible_genesis_1_expected.csv`
holds the 31 rows it wrote for that chapter in bible.csv. The booklist fixture
is the RSVCE version page cut down to its 73 book cells, and
`fixtures/bible_books_expected.txt` the names in the recorded order.
"""

import csv
from pathlib import Path

import pytest
import requests
from bs4 import BeautifulSoup

from document_lakehouse.ingestion.bible.scraper import (
    get_bible_book,
    get_bible_chapter,
    get_bible_verse,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TRANSLATION = "Revised-Standard-Version-Catholic-Edition-RSVCE-Bible"


@pytest.fixture
def expected_rows():
    with open(FIXTURES / "bible_genesis_1_expected.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_chapter_reproduces_the_recorded_rows(expected_rows, fake_get):
    calls = fake_get(
        (FIXTURES / "biblegateway_genesis_1.html").read_text(encoding="utf-8")
    )

    url, books, chapters, verses, content, hrefs, linked = get_bible_chapter(
        "RSVCE", "Genesis", 1
    )

    assert calls == [
        "https://www.biblegateway.com/passage/?search=Genesis1&version=RSVCE"
    ]
    assert [str(verse) for verse in verses] == [row["verse"] for row in expected_rows]
    assert books == [row["book"] for row in expected_rows]
    assert [str(chapter) for chapter in chapters] == [
        row["chapter"] for row in expected_rows
    ]
    assert url == [row["url"] for row in expected_rows]
    assert content == [row["content"] for row in expected_rows]
    assert hrefs == [row["hrefs"] for row in expected_rows]
    assert linked == [row["linked_content"] for row in expected_rows]


def test_first_verse_swallows_the_section_heading(expected_rows, fake_get):
    # the heading and verse 1 share the class "Gen-1-1", so both are joined
    fake_get(
        (FIXTURES / "biblegateway_genesis_1.html").read_text(encoding="utf-8")
    )

    _, _, _, _, content, _, _ = get_bible_chapter("RSVCE", "Genesis", 1)

    assert content[0].startswith("Six Days of Creation and the Sabbath")
    assert content[0] == expected_rows[0]["content"]


def test_verses_stop_at_the_first_gap(fake_get):
    fake_get(
        '<html><body><span class="Gen-1-1">one</span>'
        '<span class="Gen-1-3">three</span></body></html>'
    )

    _, _, _, verses, content, _, _ = get_bible_chapter("RSVCE", "Genesis", 1)

    assert verses == [1]
    assert content == ["one"]


def test_verse_drops_the_chapter_and_verse_numbers():
    soup = BeautifulSoup(
        '<div><span class="Gen-1-1"><span class="chapternum">1 </span>'
        '<span class="versenum">1 </span>In the beginning</span></div>',
        "html.parser",
    )

    assert get_bible_verse(soup, 1, 1) == ("In the beginning", [], [])


def test_book_list_reproduces_the_recorded_order(fake_get):
    calls = fake_get(
        (FIXTURES / "biblegateway_versions_rsvce.html").read_text(encoding="utf-8")
    )
    expected = (FIXTURES / "bible_books_expected.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    books, chapters = get_bible_book(TRANSLATION)

    assert calls == [f"https://www.biblegateway.com/versions/{TRANSLATION}/#booklist"]
    assert books == expected
    assert len(books) == 73
    assert len(chapters) == len(books)
    assert all(count.isdigit() for count in chapters)
    assert chapters[0] == "50"


def test_tries_above_the_bound_returns_an_empty_chapter(fake_get):
    """The vestigial guard: the notebook always called this with tries == 0."""
    fake_get(
        (FIXTURES / "biblegateway_genesis_1.html").read_text(encoding="utf-8")
    )

    url, books, chapters, verses, content, hrefs, linked = get_bible_chapter(
        "RSVCE", "Genesis", 1, tries=6
    )

    assert verses == []
    assert content == []
    assert url == []
    assert books == []


def test_book_list_raises_instead_of_returning_nothing(fake_get):
    fake_get("<html><body><p>no books here</p></body></html>")

    with pytest.raises(ValueError, match="no books found for translation 'no-such-translation'"):
        get_bible_book("no-such-translation")


def test_chapter_retries_a_flapping_page(monkeypatch):
    monkeypatch.setattr("document_lakehouse.ingestion.fetch.time.sleep", lambda _: None)
    html = (FIXTURES / "biblegateway_genesis_1.html").read_text(encoding="utf-8")
    calls = []

    class ServerError:
        status_code = 503

    def flapping(url, timeout=None):
        calls.append(url)
        if len(calls) < 3:
            raise requests.HTTPError("503", response=ServerError())

        class Page:
            text = html

            def raise_for_status(self):
                pass

        return Page()

    monkeypatch.setattr(requests, "get", flapping)

    _, _, _, verses, *_ = get_bible_chapter("RSVCE", "Genesis", 1)

    assert len(calls) == 3
    assert len(verses) == 31
