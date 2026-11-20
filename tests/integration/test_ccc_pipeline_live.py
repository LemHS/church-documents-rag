"""Live checks for the CCC pipeline, bounded to a couple of index rows."""

import re

import pytest

from document_lakehouse.ingestion.ccc.pipeline import build_ccc_hierarchy

pytestmark = pytest.mark.integration


def test_index_rows_come_back_with_their_paragraph_ranges():
    df = build_ccc_hierarchy(limit=2)

    assert len(df) == 2
    assert df["content"].iloc[0] == "PROLOGUE"
    assert df["hrefs"].iloc[1].endswith(".HTM")
    for count in df["number_count"]:
        assert re.fullmatch(r"\d+-\d+|", str(count))
