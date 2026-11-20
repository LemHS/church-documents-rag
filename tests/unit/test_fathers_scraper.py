"""Unit tests for the church fathers scrapers, pinned to the notebook's output."""

import pathlib

import pandas as pd
import pytest
import requests

from document_lakehouse.ingestion.fathers import scraper

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
INDEX_FIXTURE = "newadvent_fathers_index.html"
ARTICLE_FIXTURE = "newadvent_fathers_0622.html"


@pytest.fixture(scope="module")
def recorded_titles():
    """The notebook's own 420-row table, frozen as a snapshot."""
    return pd.read_csv(FIXTURES / "newadvent_fathers_titles_expected.csv", keep_default_na=False)


@pytest.fixture(scope="module")
def recorded_documents():
    """The 42 recorded rows that came from article 0622 (fathers_id 0)."""
    return pd.read_csv(FIXTURES / "newadvent_0622_expected.csv", keep_default_na=False)


@pytest.fixture
def indexPath(fake_get):
    return fake_get((FIXTURES / INDEX_FIXTURE).read_text(encoding="utf-8"))


@pytest.fixture
def articlePage(fake_get):
    return fake_get((FIXTURES / ARTICLE_FIXTURE).read_text(encoding="utf-8"))


def test_recorded_index_reproduces_the_titles_table(indexPath, recorded_titles):
    url, fathers, positions, document_types, contents, hrefs, linked = scraper.get_fathers_document_titles()

    assert url == "https://www.newadvent.org/fathers/"
    assert len(fathers) == 420 == len(recorded_titles)

    assert fathers == recorded_titles["fathers"].tolist()
    assert contents == recorded_titles["contents"].tolist()
    assert document_types == recorded_titles["document_types"].tolist()
    assert hrefs == recorded_titles["hrefs"].tolist()
    assert linked == recorded_titles["linked_contents"].tolist()
    # the CSV was written from the DataFrame, so a positions list is recorded as its repr
    assert [str(position) for position in positions] == recorded_titles["positions"].tolist()


def test_a_fathers_documents_share_one_positions_list(indexPath, recorded_titles):
    """Everything under one father points at the same list, so it ends up holding
    the father's whole set of labels. Documented, not fixed: see CONCERN.md."""
    _, fathers, positions, _, contents, _, _ = scraper.get_fathers_document_titles()

    ambrose = [i for i, father in enumerate(fathers) if father == "Ambrose (340-397)"]
    assert len(ambrose) == 11

    first, *rest = ambrose
    assert all(positions[index] is positions[first] for index in rest)
    assert positions[first] == ["[SAINT]", "[DOCTOR]"]

    recorded = recorded_titles[recorded_titles["fathers"] == "Ambrose (340-397)"]
    assert recorded["positions"].nunique() == 1
    assert recorded["positions"].iloc[0] == str(positions[first])


def test_document_types_land_on_the_document_above_them(indexPath):
    _, fathers, _, document_types, contents, _, _ = scraper.get_fathers_document_titles()

    labelled = [(content, kind) for content, kind in zip(contents, document_types) if kind]
    assert labelled, "the index page has coloured document labels"
    assert all(kind.startswith("[") for _, kind in labelled)

    # the green label is written over the document it follows, not appended
    assert len(document_types) == len(contents) == len(fathers)


def test_recorded_article_reproduces_the_documents(articlePage, recorded_documents):
    url, title, subtitles, contents, hrefs, linked = scraper.get_fathers_document(
        "https://www.newadvent.org/fathers/0622.htm"
    )

    assert url == "https://www.newadvent.org/fathers/0622.htm"
    assert title == "Epistles on Arianism and the Deposition of Arius"
    assert len(subtitles) == 42 == len(recorded_documents)

    recorded = recorded_documents[recorded_documents["fathers_id"] == 0]
    assert subtitles == recorded["subtitles"].tolist()
    assert contents == recorded["contents"].tolist()
    # hrefs and linked contents are lists here, so the CSV holds their reprs
    assert [str(href) for href in hrefs] == recorded["hrefs"].tolist()
    assert [str(linked_content) for linked_content in linked] == recorded["linked_contents"].tolist()


def test_the_about_this_page_block_is_dropped(articlePage):
    """The trailing navigation block is skipped before it becomes a row."""
    _, _, subtitles, contents, _, _ = scraper.get_fathers_document(
        "https://www.newadvent.org/fathers/0622.htm"
    )

    assert "About this page" not in subtitles
    assert all(content for content in contents)


@pytest.mark.xfail(strict=True, reason="title stays unbound when the page has no h1; CONCERN.md")
def test_page_without_a_heading_raises():
    html = "<html><body><p>text</p></body></html>"

    class Page:
        text = html

        def raise_for_status(self):
            return None

    import document_lakehouse.ingestion.fathers.scraper as module

    module_requests = module.requests
    original = module_requests.get
    module_requests.get = lambda url, timeout=None: Page()
    try:
        scraper.get_fathers_document("https://example.test/none")
    finally:
        module_requests.get = original


def test_both_requests_go_through_the_retry_policy(articlePage, monkeypatch):
    monkeypatch.setattr("document_lakehouse.ingestion.fetch.time.sleep", lambda _: None)
    html = (FIXTURES / ARTICLE_FIXTURE).read_text(encoding="utf-8")
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
                return None

        return Page()

    monkeypatch.setattr(requests, "get", flapping)

    _, title, subtitles, *_ = scraper.get_fathers_document("https://www.newadvent.org/fathers/0622.htm")

    assert len(calls) == 3
    assert title
    assert len(subtitles) == 42
