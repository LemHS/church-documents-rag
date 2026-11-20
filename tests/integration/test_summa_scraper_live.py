"""Live checks for the summa client. Opt in with `pytest -m integration`.

Read-only against the aquinas.cc API. Bounded to the window shape the notebook
relied on: `[total, [[cell_id, text], ...]]` with one cell per requested slot.
"""

import pytest

from document_lakehouse.ingestion.summa.scraper import SummaQuery, SummaTheologiae

pytestmark = pytest.mark.integration


def test_first_window_of_part_one_returns_cells():
    url, hierarchy, latin, english = SummaTheologiae().fetch(
        SummaQuery(part="I", start=0, length=20)
    )

    assert url == "https://aquinas.cc/la/en/~ST.I"
    for body in (hierarchy, latin, english):
        assert len(body) == 2
        assert len(body[1]) == 20
        assert all(len(cell) == 2 for cell in body[1])

    assert any(text for _, text in hierarchy[1])
    assert "Question 1" in " ".join(text for _, text in english[1])


def test_second_window_returns_different_cells():
    _, first, _, _ = SummaTheologiae().fetch(SummaQuery(part="I", start=0, length=20))
    _, second, _, _ = SummaTheologiae().fetch(SummaQuery(part="I", start=20, length=20))

    assert [cell_id for cell_id, _ in first[1]] != [cell_id for cell_id, _ in second[1]]


def test_part_of_part_uses_its_own_cell_tree():
    url, hierarchy, latin, english = SummaTheologiae().fetch(
        SummaQuery(part="II", part_of_part="I", start=0, length=10)
    )

    assert url == "https://aquinas.cc/la/en/~ST.I-II"
    assert len(latin[1]) == len(english[1]) == 10
