"""End-to-end church fathers scrape: the index table, then every article."""

import pandas as pd

from .scraper import get_fathers_document, get_fathers_document_titles


def fathers_titles_table():
    """The index page as one row per document, with the father it belongs to.

    `positions` and `document_types` hold the index page's labels as lists, so a
    consumer that writes the frame to CSV gets their reprs.
    """
    url, fathers, positions, document_types, contents, hrefs, linked_contents = get_fathers_document_titles()

    return pd.DataFrame({
        "url": [url] * len(contents),
        "fathers": fathers,
        "positions": positions,
        "document_types": document_types,
        "contents": contents,
        "hrefs": hrefs,
        "linked_contents": linked_contents,
    })


def document_urls(titles):
    """Absolute URL of each document, from `fathers_titles_table()`."""
    return titles["url"] + titles["hrefs"]


def scrape_fathers_documents(urls=None):
    """Every section of every article, one row per section.

    `urls` defaults to the documents listed by the index page. `fathers_id` is
    the position of the URL in that list, which is the row of the title table it
    came from. A document that fails raises: the run has no failure budget, so
    one bad article ends the scrape.
    """
    if urls is None:
        urls = document_urls(fathers_titles_table())

    dct = {
        "fathers_id": [],
        "title": [],
        "subtitles": [],
        "contents": [],
        "hrefs": [],
        "linked_contents": []
    }

    for i, url in enumerate(urls):
        url, title, subtitles, contents, hrefs, linked_contents = get_fathers_document(url)

        dct["fathers_id"] += [i] * len(subtitles)
        dct["title"] += [title] * len(subtitles)
        dct["subtitles"] += subtitles
        dct["contents"] += contents
        dct["hrefs"] += hrefs
        dct["linked_contents"] += linked_contents

    return pd.DataFrame(dct)
