"""Live checks for the church fathers pipeline, read-only."""

import pytest

from document_lakehouse.ingestion.fathers.pipeline import (
    document_urls,
    fathers_titles_table,
    scrape_fathers_documents,
)

pytestmark = pytest.mark.integration


def test_the_index_yields_one_absolute_url_per_document():
    titles = fathers_titles_table()
    urls = document_urls(titles)

    assert len(titles) > 300
    assert len(urls) == len(titles)
    assert all(url.startswith("https://www.newadvent.org/fathers/") for url in urls)
    assert all(url.endswith(".htm") for url in urls)


def test_one_article_comes_through_the_pipeline():
    frame = scrape_fathers_documents(["https://www.newadvent.org/fathers/0622.htm"])

    assert len(frame) > 40
    assert frame["fathers_id"].tolist() == [0] * len(frame)
    assert frame["title"].unique().tolist() == ["Epistles on Arianism and the Deposition of Arius"]
    assert all(frame["contents"])
