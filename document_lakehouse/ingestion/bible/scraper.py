import regex as re
import requests
from bs4 import BeautifulSoup

from ..contents import get_contents
from ..fetch import call


def get_bible_verse(soup, chapter, verse):
    text = soup.find_all(class_=re.compile(f"{chapter}-{verse}$"))

    return get_contents(text, excludes=[("class", "chapternum"), ("class", "versenum")])


def get_bible_chapter(translation, book, chapter, tries=0):
    url = f"https://www.biblegateway.com/passage/?search={book}{chapter}&version={translation}"
    
    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")

    verse_exhausted = False
    verse = 1

    verse_lst, contents_lst, hrefs_lst, linked_content_lst = [], [], [], []

    while not verse_exhausted and (tries <= 5):
        contents, hrefs, linked_content = get_bible_verse(soup, chapter, verse)
        if not contents:
            verse_exhausted = True
            continue

        verse_lst.append(verse)
        contents_lst.append(contents)
        hrefs_lst.append(";".join(hrefs))
        linked_content_lst.append(";".join(linked_content))

        verse += 1

    return [url] * (verse - 1), [book] * (verse - 1), [chapter] * (verse - 1), verse_lst, contents_lst, hrefs_lst, linked_content_lst


def get_bible_book(translation):
    books = []
    chapters_num = []

    url = f"https://www.biblegateway.com/versions/{translation}/#booklist"

    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")
    contents = soup.find_all(attrs={"class": "book-name"})

    if not contents:
        raise ValueError(f"no books found for translation {translation!r} at {url}")

    for content in contents:
        books.append(content.find(string=True, recursive=False).strip())
        chapters_num.append(content.find(attrs={"class": "num-chapters"}).text)

    return books, chapters_num
