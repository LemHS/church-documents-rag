"""Live checks for the church fathers scrapers, read-only."""

import pytest

from document_lakehouse.ingestion.fathers.scraper import (
    get_fathers_document,
    get_fathers_document_titles,
)

pytestmark = pytest.mark.integration


def test_index_still_lists_the_fathers_and_their_documents():
    url, fathers, positions, document_types, contents, hrefs, linked_contents = get_fathers_document_titles()

    assert url == "https://www.newadvent.org/fathers/"
    assert len(contents) > 300
    assert all(href.endswith(".htm") for href in hrefs)
    assert all(father for father in fathers)
    assert len(hrefs) == len(contents) == len(fathers)


def test_one_article_still_comes_back_with_its_sections():
    url, title, subtitles, contents, hrefs, linked_contents = get_fathers_document(
        "https://www.newadvent.org/fathers/0622.htm"
    )

    assert url == "https://www.newadvent.org/fathers/0622.htm"
    assert title == "Epistles on Arianism and the Deposition of Arius"
    assert len(subtitles) > 40
    assert all(content for content in contents)
    assert "About this page" not in subtitles
