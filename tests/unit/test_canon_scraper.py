"""Unit tests for the canon scraper, pinned to a recorded canonlaw.ninja page.

`fixtures/canonlaw_canon_350.html` is canon 350 as fetched by the notebook.
The breadcrumb order asserted below is the one its docstring recorded.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from document_lakehouse.ingestion.canon.scraper import (
    get_canon,
    get_metadata,
    metadata_to_nested,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CANON_350_BREADCRUMB = [
    "The People of God",
    "The Hierarchical Constitution of the Church",
    "The Supreme Authority of the Church",
    "The Cardinals of the Holy Roman Church",
]


def element(html):
    return BeautifulSoup(html, "html.parser")


def test_canon_page_returns_text_and_breadcrumb(fake_get):
    calls = fake_get(
        (FIXTURES / "canonlaw_canon_350.html").read_text(encoding="utf-8")
    )

    url, content, hrefs, linked, metadata = get_canon(350)

    assert url == "https://canonlaw.ninja/?nums=350"
    assert calls == [url]
    assert metadata == CANON_350_BREADCRUMB
    assert "The College of Cardinals is divided into three orders" in content
    # the trailing cross-link in canon 350 points at itself
    assert hrefs == ["?nums=350"]
    assert linked == ["can. 350"]


def test_canon_past_the_end_returns_the_alert_as_content(fake_get):
    fake_get((FIXTURES / "canonlaw_no_results.html").read_text(encoding="utf-8"))

    url, content, hrefs, linked, metadata = get_canon(9999)

    assert url == "https://canonlaw.ninja/?nums=9999"
    assert content == "No results found."
    assert hrefs == []
    assert linked == []
    assert metadata == []


def test_breadcrumb_comes_back_parent_first():
    soup = element(
        '<div><a class="badge-secondary">Part</a>'
        '<a class="badge-secondary">Section</a>'
        '<div class="text-dark mb-3">canon text</div></div>'
    )
    text = soup.find(attrs={"class": "text-dark mb-3"})

    assert get_metadata(text) == ["Part", "Section"]


def test_breadcrumb_collapses_whitespace():
    soup = element(
        '<div><a class="badge-secondary">  The   People\n of  God </a>'
        '<div class="text-dark mb-3">canon text</div></div>'
    )
    text = soup.find(attrs={"class": "text-dark mb-3"})

    assert get_metadata(text) == ["The People of God"]


def test_breadcrumb_is_empty_without_badges():
    soup = element('<div class="text-dark mb-3">canon text</div>')
    text = soup.find(attrs={"class": "text-dark mb-3"})

    assert get_metadata(text) == []
    assert get_metadata(None) == []


def test_breadcrumb_nests_one_level_per_label():
    assert metadata_to_nested(CANON_350_BREADCRUMB) == {
        "The People of God": {
            "The Hierarchical Constitution of the Church": {
                "The Supreme Authority of the Church": {
                    "The Cardinals of the Holy Roman Church": {}
                }
            }
        }
    }
    assert metadata_to_nested([]) == {}
