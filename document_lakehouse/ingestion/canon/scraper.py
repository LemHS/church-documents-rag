import requests
from bs4 import BeautifulSoup, Tag

from ..contents import get_contents
from ..fetch import call


def get_metadata(text):
    """Collect the hierarchical category breadcrumb shown above a canon.

    On canonlaw.ninja, one or more `a.badge-secondary` badges sit just above
    the canon text. They are ordered from the broadest book/part down to the
    most specific section, e.g. for canon 350:

        ["The People of God",
         "The Hierarchical Constitution of the Church",
         "The Supreme Authority of the Church",
         "The Cardinals of the Holy Roman Church"]

    Returns the list in that parent -> child order.
    Returns an empty list when the canon has no breadcrumb, or when `text` is
    None because the canon number is past the end of the Code (canonlaw.ninja
    still answers HTTP 200 in that case, but renders an
    "alert alert-secondary" saying "No results found." instead of the canon).
    """
    if text is None:
        # out-of-range canon number: there is no canon, hence no hierarchy
        return []

    metadata = []
    for sibling in text.previous_siblings:
        # skip whitespace / blank text nodes between badges
        if not isinstance(sibling, Tag):
            continue
        if sibling.name == "a" and "badge-secondary" in sibling.get("class", []):
            metadata.append(" ".join(sibling.get_text(" ", strip=True).split()))
        else:
            break
    return list(reversed(metadata))


def metadata_to_nested(metadata):
    """Turn an ordered breadcrumb list into a nested dict hierarchy,
    e.g. ["X", "Y"] -> {"X": {"Y": {}}}."""
    nested = {}
    for label in reversed(metadata):
        nested = {label: nested}
    return nested


def get_canon(canon_number):
    url = f"https://canonlaw.ninja/?nums={canon_number}"

    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.find(attrs={"class" : "text-dark mb-3"})

    metadata = get_metadata(text)

    if text is None:
        # canon number is past the last canon: the page has no canon text, only
        # a "No results found." alert. Return that as content so the caller's
        # `"No results" in content` check can skip this number.
        no_results = soup.find(attrs={"class": "alert alert-secondary"})
        content = no_results.get_text(" ", strip=True) if no_results else "No results found."
        return url, content, [], [], metadata

    return url, *get_contents(text.contents[1:]), metadata
