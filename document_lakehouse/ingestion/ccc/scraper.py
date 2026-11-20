import requests
from bs4 import BeautifulSoup
import regex as re

from ..contents import get_contents
from ..fetch import call


def get_ccc(ccc_paragraph):
    url = f"https://canonlaw.ninja/?v=ccc&nums={ccc_paragraph}"

    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.find(attrs={"class" : "text-dark mb-3"})

    return url, *get_contents(text.contents[1:])


def get_ccc_index():
    def recursive_find(indexes):
        contents_lst = []
        hrefs_lst = []
        linked_contents_lst = []
        for index in indexes:
            if len(new_indexes := index.contents) > 1:
                contents, hrefs, linked_contents = recursive_find([new_indexes[0]])

                contents_lst += contents
                hrefs_lst += hrefs
                linked_contents_lst += linked_contents
            else:
                contents, hrefs, linked_contents = get_contents([index])

                contents_lst.append(contents)
                if hrefs:
                    hrefs_lst += hrefs
                    linked_contents_lst += linked_contents
                else:
                    hrefs_lst.append("")
                    linked_contents_lst.append("")

        return contents_lst, hrefs_lst, linked_contents_lst

    url = f"https://www.vatican.va/archive/ENG0015/_INDEX.HTM"

    response = call(lambda: requests.get(url, timeout=10), url)

    soup = BeautifulSoup(response.text, "html.parser")
    indexes = soup.find_all("li")

    return url, *recursive_find(indexes)


def get_ccc_hierarchy(contents, hrefs, linked_contents):
    def check_hierarchy(content, hierarchies, fallback):
        trigger = False
        hierarchies_value = {}
        for hierarchy, regex_patterns in hierarchies:
            hierarchies_value[hierarchy] = ""
            for regex_pattern in regex_patterns:
                if re.match(regex_pattern, content):
                    trigger = True
                    hierarchies_value[hierarchy] = content

        if trigger:
            hierarchies_value[fallback] = ""
        else:
            hierarchies_value[fallback] = content

        return hierarchies_value

        
    
    hierarchies = [
        ("part", [r"^PROLOGUE$", r"^PART.:"]),
        ("section", [r"^SECTION"]),
        ("chapter", [r"^CHAPTER"]),
        ("article", [r"^Article"])
    ]

    hierarchy_dct = {
        "part": [],
        "section": [],
        "chapter": [],
        "article": [],
        "roman_numeral": [],
        "content": [],
        "hrefs": [],
        "linked_content": []
    }

    

    for content, href, linked_content in zip(contents, hrefs, linked_contents):
        hierarchies_value = check_hierarchy(content, hierarchies, "roman_numeral")
        for key, value in hierarchies_value.items():
            hierarchy_dct[key].append(value)
        hierarchy_dct["content"].append(content)
        hierarchy_dct["hrefs"].append(href)
        hierarchy_dct["linked_content"].append(linked_content)

    return hierarchy_dct


def get_ccc_number_range(ccc_hierarchy_df, id):
    def count_number(contents):
        numbers = []
        for content in contents:
            if number := re.match(r"^[0-9]*(?=(\r|\s))", content.text):
                if number.group():
                    numbers.append(int(number.group()))
        return numbers

    def to_range(numbers):
        if not numbers:
            return ""
        return f"{min(numbers)}-{max(numbers)}"

    number_counts = []
    url = "https://www.vatican.va/archive/ENG0015/{}"

    try:
        for i in range(id, len(ccc_hierarchy_df["hrefs"])):
            href = ccc_hierarchy_df["hrefs"][i]
            if href:
                page = url.format(href)
                response = call(lambda: requests.get(page, timeout=10), page)

                soup = BeautifulSoup(response.text, "html.parser")
                contents = soup.find_all(attrs={"class": "MsoNormal"})
                number_counts.append(to_range(count_number(contents)))
            else:
                number_counts.append("")
    finally:
        # on failure the caller still gets the rows that did come back; rows the
        # run never reached stay None
        column = [None] * id + number_counts
        column += [None] * (len(ccc_hierarchy_df["hrefs"]) - len(column))
        ccc_hierarchy_df["number_count"] = column

    return ccc_hierarchy_df
