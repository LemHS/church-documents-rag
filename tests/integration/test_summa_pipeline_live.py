"""Live check for the Summa pipeline, bounded to two windows."""

import pytest

from document_lakehouse.ingestion.summa.pipeline import scrape_summa

pytestmark = pytest.mark.integration


def test_two_windows_of_the_first_part():
    df = scrape_summa(partis=(("I",),), length=20, max_windows=2)

    assert len(df) == 40
    assert df["eng"].iloc[0] == "Summa Theologiae First Part"
    assert "Question 1" in df["eng"].tolist()
