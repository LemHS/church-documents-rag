"""End-to-end CCC scrape: index page -> hierarchy table -> paragraph ranges."""

import pandas as pd

from .scraper import get_ccc_hierarchy, get_ccc_index, get_ccc_number_range


def build_ccc_hierarchy(start=0, limit=None):
    """Build the CCC hierarchy table, one row per entry of the vatican.va index.

    `limit` keeps only the first rows of the index before the paragraph page for
    each row is fetched — for smoke runs, not for a full dataset.
    """
    _, contents, hrefs, linked_contents = get_ccc_index()
    hierarchy_dct = get_ccc_hierarchy(contents, hrefs, linked_contents)

    ccc_hierarchy_df = pd.DataFrame(hierarchy_dct)

    if limit is not None:
        ccc_hierarchy_df = ccc_hierarchy_df.head(limit)

    return get_ccc_number_range(ccc_hierarchy_df, start)
