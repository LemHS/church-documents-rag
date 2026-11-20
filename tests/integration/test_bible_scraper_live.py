"""Live checks for the bible scraper. Opt in with `pytest -m integration`.

Read-only. Bounded to what the notebook recorded: 31 verses in Genesis 1 and
73 books in the RSVCE canon, in the same order.
"""

from pathlib import Path

import pytest

from document_lakehouse.ingestion.bible.scraper import get_bible_book, get_bible_chapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TRANSLATION = "Revised-Standard-Version-Catholic-Edition-RSVCE-Bible"

pytestmark = pytest.mark.integration


def test_genesis_1_still_returns_31_verses():
    url, books, chapters, verses, content, hrefs, linked = get_bible_chapter(
        "RSVCE", "Genesis", 1
    )

    assert url[0] == "https://www.biblegateway.com/passage/?search=Genesis1&version=RSVCE"
    assert verses == list(range(1, 32))
    assert len(content) == len(hrefs) == len(linked) == 31
    assert "In the beginning God created" in content[0]
    assert all(href.startswith("#") for href in hrefs[0].split(";") if href)


def test_booklist_still_matches_the_recorded_order():
    expected = (FIXTURES / "bible_books_expected.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    books, chapters = get_bible_book(TRANSLATION)

    assert books == expected
    assert len(chapters) == 73
    assert chapters[books.index("Genesis")] == "50"
    assert chapters[books.index("Revelation")] == "22"
