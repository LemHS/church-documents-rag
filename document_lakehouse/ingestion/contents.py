from bs4 import Tag


def get_contents(contents, excludes=[]):
    content_list = []
    linked_content = []
    hrefs = []
    for content in contents:
        if isinstance(content, str):
            content_list.append(content.strip(" "))
        else:
            if any(exclude in content.get(attr, []) for attr, exclude in excludes):
                continue
            
            extracted_content, href, extracted_linked_content = get_contents(content.contents, excludes)

            if content.has_attr("href"):
                hrefs.append(content.get("href"))
                linked_content.append(extracted_content)

            content_list.append(extracted_content.strip(" "))
            linked_content += extracted_linked_content
            hrefs += href

    return ' '.join(content_list), hrefs, linked_content
