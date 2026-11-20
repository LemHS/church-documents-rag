"""Unit tests for the HTML walker shared by the scrapers."""

from bs4 import BeautifulSoup

from document_lakehouse.ingestion.contents import get_contents


def element(html):
    return BeautifulSoup(html, "html.parser").find("div")


def test_plain_text_is_joined_and_trimmed():
    assert get_contents(["  Genesis  ", " 1  "]) == ("Genesis 1", [], [])


def test_link_contributes_its_href_and_linked_text():
    div = element('<div><a href="__P1.HTM">PROLOGUE</a></div>')

    assert get_contents([div]) == ("PROLOGUE", ["__P1.HTM"], ["PROLOGUE"])


def test_excluded_attributes_are_dropped():
    """`excludes` is a list of (attribute, value) pairs, checked against the tag."""
    div = element('<div><span class="versenum">1</span>In the beginning</div>')

    assert get_contents([div], excludes=[("class", "versenum")]) == ("In the beginning", [], [])


def test_an_unlisted_value_is_kept():
    div = element('<div><span class="versenum">1</span>In the beginning</div>')

    assert get_contents([div], excludes=[("class", "chapternum")]) == ("1 In the beginning", [], [])


def test_a_missing_attribute_does_not_drop_the_tag():
    div = element('<div><span class="versenum">1</span>In the beginning</div>')

    assert get_contents([div], excludes=[("id", "src")]) == ("1 In the beginning", [], [])


def test_nested_links_keep_their_order():
    div = element('<div><a href="a.HTM">One</a> and <a href="b.HTM">Two</a></div>')

    content, hrefs, linked = get_contents([div])

    assert content == "One and Two"
    assert hrefs == ["a.HTM", "b.HTM"]
    assert linked == ["One", "Two"]
