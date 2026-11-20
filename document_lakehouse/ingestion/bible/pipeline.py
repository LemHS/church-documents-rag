"""End-to-end bible scrape: every chapter of every book of one translation."""

import logging

import pandas as pd

from ..failures import attach
from .scraper import get_bible_book, get_bible_chapter

log = logging.getLogger(__name__)

VERSIONS_SLUG = "Revised-Standard-Version-Catholic-Edition-RSVCE-Bible"


def scrape_bible(versions_slug=VERSIONS_SLUG, translation="RSVCE", max_failures=5):
    """Scrape every chapter of the booklist behind `versions_slug`.

    `max_failures` is the number of chapters the run may lose before it gives
    up; the counter spans the whole run, not one book. Every skipped chapter is
    recorded in `frame.attrs["failures"]` with its book and chapter.
    """
    bible_book, bible_num_chapters = get_bible_book(versions_slug)

    bible_book_chapters = list(zip(bible_book, bible_num_chapters))

    dct = {"book": [],
           "chapter": [],
           "verse": [],
           "url": [],
           "content": [],
           "linked_content": [],
           "hrefs": []}

    done_bible_book = []
    current_book_chapter = 0

    failures = []
    tries = 0

    for bible_book, bible_num_chapters in bible_book_chapters:

        if bible_book in done_bible_book:
            continue

        for chapter_num in range(1, int(bible_num_chapters) + 1):
            if chapter_num <= current_book_chapter:
                continue

            try:
                url, bible_books, chapter_nums, verses, content, hrefs, linked_content = get_bible_chapter(translation, bible_book, chapter_num)

                dct["book"] += bible_books
                dct["chapter"] += chapter_nums
                dct["verse"] += verses
                dct["url"] += url
                dct["content"] += content
                dct["linked_content"] += linked_content
                dct["hrefs"] += hrefs

            except Exception as e:
                failures.append({"book": bible_book, "chapter": chapter_num, "reason": "error", "error": str(e)})
                if tries < max_failures:
                    log.warning("%s %s failed (%s/%s): %s", bible_book, chapter_num, tries + 1, max_failures, e)
                else:
                    raise
                tries += 1
                continue

            current_book_chapter = chapter_num
        else:
            current_book_chapter = 0

        done_bible_book.append(bible_book)

    return attach(pd.DataFrame(dct).drop_duplicates(), failures, lambda failure: f"{failure['book']} {failure['chapter']}")
