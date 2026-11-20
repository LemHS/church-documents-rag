import requests
from bs4 import BeautifulSoup
import regex as re

from ..contents import get_contents
from ..fetch import call


def get_fathers_document_titles():
    url = f"https://www.newadvent.org/fathers/"

    contents = []
    hrefs = []
    linked_contents = []

    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")

    father = ""
    fathers = []

    position = []
    positions = []

    document_types = []

    titles = soup.find_all(
        lambda tag: (
            tag.name == "a" and tag.has_attr("href")
            and re.search(r"fathers/[0-9]*\.htm", tag["href"])
        ) or tag.name == "font" or tag.name == "strong"
    )
    for title in titles:
        if title.name == "strong":
            father = title.text
            position = []
        elif title.name == "font" and title.get("color", "") != "#007700":
            position.append(title.text)
        elif title.name == "font" and title.get("color", "") == "#007700":
            document_types[-1] = title.text
        else:
            content, href, linked_content = get_contents([title])
            fathers.append(father)
            positions.append(position)
            document_types.append("")
            contents.append(content)
            hrefs += href
            linked_contents += linked_content

    return url, fathers, positions, document_types, contents, hrefs, linked_contents


def get_fathers_document(url):
    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")

    texts = soup.find_all(("h1", "h2", "p"))

    subtitle = ""
    subtitles = []
    contents = []
    hrefs = []
    linked_contents = []

    for text in texts:
        if text.name == "h1":
            title = text.text
        elif text.name == "h2":
            subtitle = text.text
        else:
            content, href, linked_content = get_contents([text], excludes=[("href", "gumroad"), ("id", "src"), ("id", "contactus"), ("href", "contactus")])
            if (not content) or (subtitle == "About this page"):
                continue

            subtitles.append(subtitle)
            contents.append(content)
            hrefs.append(href)
            linked_contents.append(linked_content)


    return url, title, subtitles, contents, hrefs, linked_contents
