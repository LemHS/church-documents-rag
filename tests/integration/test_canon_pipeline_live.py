"""Live checks for the canon pipeline, bounded to three canons."""

import pytest

from document_lakehouse.ingestion.canon.pipeline import scrape_canon

pytestmark = pytest.mark.integration


def test_three_canons_come_back_with_their_breadcrumb():
    df = scrape_canon(max_id=3)

    assert df["id"].tolist() == [0, 1, 2]
    assert df["url"].iloc[0] == "https://canonlaw.ninja/?nums=0"
    assert df["metadata"].iloc[0] == "General Norms"
    assert df["content"].str.len().min() > 20
