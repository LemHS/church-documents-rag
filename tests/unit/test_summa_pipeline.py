"""Unit tests for the Summa Theologiae pipeline driver loop."""

import pytest

import document_lakehouse.ingestion.summa.pipeline as summa_pipeline


class FakeQuery:
    def __init__(
        self,
        part,
        part_of_part=None,
        start=0,
        length=36,
        did_hierarchy=-15,
        did_lang1=56,
        did_lang2=57,
    ):
        self.part = part
        self.part_of_part = part_of_part
        self.start = start
        self.length = length
        self.did_hierarchy = did_hierarchy
        self.did_lang1 = did_lang1
        self.did_lang2 = did_lang2


class FakeSumma:
    def __init__(self, totals=None, failures=None, default_total=0):
        self.totals = dict(totals or {})
        self.default_total = default_total
        self.failures = dict(failures or {})
        self.queries = []

    def fetch(self, query):
        self.queries.append(query)
        window = (query.part, query.part_of_part, query.start)
        if self.failures.get(window, 0) > 0:
            self.failures[window] -= 1
            raise RuntimeError("that window is down")

        total = self.totals.get((query.part, query.part_of_part), self.default_total)
        cells = [
            (1000 + query.start + n, f"{query.part}[{query.start + n}]")
            for n in range(min(query.length, max(0, total - query.start)))
        ]
        return (
            f"https://aquinas.cc/la/en/~ST.{query.part}",
            [total, cells],
            [total, [(cid, text + " (la)") for cid, text in cells]],
            [total, [(cid, text + " (en)") for cid, text in cells]],
        )


def install(monkeypatch, client):
    monkeypatch.setattr(summa_pipeline, "SummaQuery", FakeQuery)
    monkeypatch.setattr(summa_pipeline, "SummaTheologiae", lambda: client)
    return client


def test_windows_walk_a_part_until_it_runs_dry(monkeypatch):
    client = install(monkeypatch, FakeSumma(totals={("I", None): 25}, default_total=25))

    df = summa_pipeline.scrape_summa(partis=(("I",),), length=20)

    assert [query.start for query in client.queries] == [0, 20, 40]
    assert len(df) == 25
    assert list(df.columns) == ["hierarchy", "latin", "eng"]
    assert df.loc[0, "hierarchy"] == "I[0]"
    assert df.loc[0, "latin"] == "I[0] (la)"
    assert df.loc[0, "eng"] == "I[0] (en)"
    assert df.loc[24, "hierarchy"] == "I[24]"


def test_every_part_is_reached_with_its_own_dids(monkeypatch):
    client = install(monkeypatch, FakeSumma())

    df = summa_pipeline.scrape_summa()

    assert [(q.part_of_part, q.part) for q in client.queries] == [
        (None, "I"),
        (None, "I"),
        ("I", "II"),
        ("II", "II"),
        (None, "III"),
        (None, "III"),
    ]
    assert [(q.did_hierarchy, q.did_lang1, q.did_lang2) for q in client.queries] == [
        (-15, 56, 57),
        (-16, 60, 61),
        (-17, 64, 65),
        (-18, 68, 69),
        (-19, 72, 73),
        (-20, 76, 77),
    ]
    assert [query.start for query in client.queries] == [0] * 6
    assert len(df) == 0


def test_max_windows_stops_a_smoke_run(monkeypatch):
    client = install(monkeypatch, FakeSumma(default_total=25))

    df = summa_pipeline.scrape_summa(length=20, max_windows=2)

    assert [query.start for query in client.queries] == [0, 20]
    # 20 cells in the first window, the 5 that are left in the second
    assert len(df) == 25


def test_a_flapping_window_is_retried(monkeypatch):
    client = install(
        monkeypatch,
        FakeSumma(totals={("I", None): 20}, failures={("I", None, 0): 2}),
    )

    df = summa_pipeline.scrape_summa(partis=(("I",),), length=20)

    assert len(df) == 20
    # two failed attempts, the window itself, then the empty window that ends the part
    assert len(client.queries) == 4
    # the window came back, and the report says so instead of hiding the retry
    assert [(failure["part"], failure["start"], failure["recovered"]) for failure in df.attrs["failures"]] == [
        ("I", 0, True),
        ("I", 0, True),
    ]


def test_giving_up_raises_once_the_budget_is_spent(monkeypatch):
    install(monkeypatch, FakeSumma(failures={("I", None, 0): 99}))

    with pytest.raises(RuntimeError, match="that window is down"):
        summa_pipeline.scrape_summa(partis=(("I",),), max_failures=2)
