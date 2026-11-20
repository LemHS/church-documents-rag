"""Unit tests for the church fathers pipeline."""

import pathlib

import pandas as pd
import pytest

import document_lakehouse.ingestion.fathers.pipeline as fathers_pipeline

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"

COLUMNS = ["fathers_id", "title", "subtitles", "contents", "hrefs", "linked_contents"]


def make_titles(fathers, hrefs):
    url = "https://www.newadvent.org/fathers/"

    def get_fathers_document_titles():
        return url, list(fathers), [[] for _ in fathers], ["" for _ in fathers], list(fathers), list(hrefs), [[] for _ in fathers]

    return get_fathers_document_titles


def make_document(sections):
    """`sections` maps a url to how many sections it comes back with."""
    asked = []

    def get_fathers_document(url):
        asked.append(url)
        count = sections[url]
        return (
            url,
            f"title of {url.rsplit('/', 1)[-1]}",
            [f"section {n}" for n in range(count)],
            [f"content {n}" for n in range(count)],
            [[f"{n}.htm"] for n in range(count)],
            [[f"link {n}"] for n in range(count)],
        )

    get_fathers_document.asked = asked
    return get_fathers_document


def test_the_title_table_has_the_notebook_columns(monkeypatch):
    monkeypatch.setattr(
        fathers_pipeline,
        "get_fathers_document_titles",
        make_titles(["Augustine (354-430)"], ["0123.htm"]),
    )

    titles = fathers_pipeline.fathers_titles_table()

    assert list(titles.columns) == [
        "url", "fathers", "positions", "document_types", "contents", "hrefs", "linked_contents",
    ]
    assert titles.loc[0, "url"] == "https://www.newadvent.org/fathers/"
    assert titles.loc[0, "fathers"] == "Augustine (354-430)"
    assert titles.loc[0, "hrefs"] == "0123.htm"


def test_document_urls_joins_the_index_url_and_the_href(monkeypatch):
    monkeypatch.setattr(
        fathers_pipeline,
        "get_fathers_document_titles",
        make_titles(["Ambrose (340-397)"], ["0567.htm"]),
    )

    urls = fathers_pipeline.document_urls(fathers_pipeline.fathers_titles_table())

    assert urls.tolist() == ["https://www.newadvent.org/fathers/0567.htm"]


def test_each_document_becomes_one_row_per_section(monkeypatch):
    urls = ["https://www.newadvent.org/fathers/0001.htm", "https://www.newadvent.org/fathers/0002.htm"]
    fake = make_document({urls[0]: 2, urls[1]: 1})
    monkeypatch.setattr(fathers_pipeline, "get_fathers_document", fake)

    frame = fathers_pipeline.scrape_fathers_documents(urls)

    assert list(frame.columns) == COLUMNS
    assert frame["fathers_id"].tolist() == [0, 0, 1]
    assert frame["title"].tolist() == ["title of 0001.htm"] * 2 + ["title of 0002.htm"]
    assert frame["subtitles"].tolist() == ["section 0", "section 1", "section 0"]
    assert frame["contents"].tolist() == ["content 0", "content 1", "content 0"]
    assert frame["hrefs"].tolist() == [["0.htm"], ["1.htm"], ["0.htm"]]


def test_the_index_is_the_default_source_of_urls(monkeypatch):
    monkeypatch.setattr(
        fathers_pipeline,
        "get_fathers_document_titles",
        make_titles(["Augustine (354-430)", "Ambrose (340-397)"], ["0001.htm", "0002.htm"]),
    )
    urls = ["https://www.newadvent.org/fathers/0001.htm", "https://www.newadvent.org/fathers/0002.htm"]
    fake = make_document({url: 1 for url in urls})
    monkeypatch.setattr(fathers_pipeline, "get_fathers_document", fake)

    frame = fathers_pipeline.scrape_fathers_documents()

    assert fake.asked == urls
    assert frame["fathers_id"].tolist() == [0, 1]


def test_explicit_urls_skip_the_index(monkeypatch):
    def titles_must_not_be_called():
        raise AssertionError("the index page is only fetched when urls are not given")

    monkeypatch.setattr(fathers_pipeline, "get_fathers_document_titles", titles_must_not_be_called)
    url = "https://www.newadvent.org/fathers/0003.htm"
    monkeypatch.setattr(fathers_pipeline, "get_fathers_document", make_document({url: 1}))

    frame = fathers_pipeline.scrape_fathers_documents([url])

    assert frame.loc[0, "fathers_id"] == 0


def test_a_document_with_no_sections_holds_its_slot(monkeypatch):
    urls = ["https://www.newadvent.org/fathers/0001.htm", "https://www.newadvent.org/fathers/0002.htm"]
    fake = make_document({urls[0]: 2, urls[1]: 0})
    monkeypatch.setattr(fathers_pipeline, "get_fathers_document", fake)

    frame = fathers_pipeline.scrape_fathers_documents(urls)

    # nothing to add for the empty document, but the next one keeps its index
    assert frame["fathers_id"].tolist() == [0, 0]
    assert len(frame) == 2


def test_a_failed_document_ends_the_run(monkeypatch):
    """There is no failure budget here: the run has nothing to hand back."""
    urls = ["https://www.newadvent.org/fathers/0001.htm", "https://www.newadvent.org/fathers/0002.htm"]
    fake = make_document({urls[0]: 1, urls[1]: 1})

    def failing(url):
        if url == urls[1]:
            raise ConnectionError("0002.htm is down")
        return fake(url)

    monkeypatch.setattr(fathers_pipeline, "get_fathers_document", failing)

    with pytest.raises(ConnectionError, match="0002.htm is down"):
        fathers_pipeline.scrape_fathers_documents(urls)


def test_recorded_article_comes_through_the_pipeline(monkeypatch, fake_get):
    fake_get((FIXTURES / "newadvent_fathers_0622.html").read_text(encoding="utf-8"))
    recorded = pd.read_csv(FIXTURES / "newadvent_0622_expected.csv", keep_default_na=False)

    frame = fathers_pipeline.scrape_fathers_documents(["https://www.newadvent.org/fathers/0622.htm"])

    assert frame.shape == (42, 6)
    assert list(frame.columns) == COLUMNS
    assert frame["subtitles"].tolist() == recorded["subtitles"].tolist()
    assert frame["contents"].tolist() == recorded["contents"].tolist()
    assert frame["fathers_id"].tolist() == [0] * 42
    assert frame["title"].unique().tolist() == ["Epistles on Arianism and the Deposition of Arius"]
