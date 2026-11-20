"""Unit tests for the canon pipeline driver loop."""

import logging

import pytest

import document_lakehouse.ingestion.canon.pipeline as canon_pipeline


def make_get_canon(answer_for):
    calls = []

    def get_canon(number):
        calls.append(number)
        answer = answer_for(number)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, str):
            return f"https://canonlaw.ninja/?nums={number}", answer, [], [], []
        return answer

    get_canon.calls = calls
    return get_canon


CANON_0 = ("https://canonlaw.ninja/?nums=0", "content zero", ["?nums=0"], ["can. 0"], ["General Norms"])


def test_max_id_caps_the_run(monkeypatch):
    fake = make_get_canon(lambda number: ("u", f"content {number}", [], [], []))
    monkeypatch.setattr(canon_pipeline, "get_canon", fake)

    df = canon_pipeline.scrape_canon(max_id=3)

    assert df["id"].tolist() == [0, 1, 2]
    assert fake.calls == [0, 1, 2]


def test_columns_keep_the_notebook_order_and_join_lists(monkeypatch):
    fake = make_get_canon(
        lambda number: (
            "https://canonlaw.ninja/?nums=0",
            "content zero",
            ["?nums=0", "?nums=1"],
            ["can. 0", "can. 1"],
            ["General Norms", "Book I"],
        )
        if number == 0
        else "No results found."
    )
    monkeypatch.setattr(canon_pipeline, "get_canon", fake)

    df = canon_pipeline.scrape_canon(max_id=10, max_failures=0)

    assert list(df.columns) == ["id", "url", "metadata", "content", "linked_content", "hrefs"]
    assert df.loc[0, "metadata"] == "General Norms > Book I"
    assert df.loc[0, "linked_content"] == "can. 0;can. 1"
    assert df.loc[0, "hrefs"] == "?nums=0;?nums=1"


def test_no_results_burns_the_failure_budget(monkeypatch):
    fake = make_get_canon(lambda number: CANON_0 if number == 0 else "No results found.")
    monkeypatch.setattr(canon_pipeline, "get_canon", fake)

    df = canon_pipeline.scrape_canon(max_id=10, max_failures=2)

    assert df["id"].tolist() == [0]
    # a missing number is asked again, not skipped: the budget ends the run
    assert fake.calls == [0, 1, 1, 1]
    # every miss is on the frame, so a hole in the table can be named afterwards
    assert df.attrs["failures"] == [
        {"id": 1, "reason": "no results", "error": ""},
        {"id": 1, "reason": "no results", "error": ""},
        {"id": 1, "reason": "no results", "error": ""},
    ]


def test_a_failed_request_is_logged_and_the_same_number_is_asked_again(monkeypatch, caplog):
    state = {"failed": False}

    def answer_for(number):
        if number == 0 and not state["failed"]:
            state["failed"] = True
            return RuntimeError("502 bad gateway")
        return "u", f"content {number}", [], [], []

    fake = make_get_canon(answer_for)
    monkeypatch.setattr(canon_pipeline, "get_canon", fake)

    with caplog.at_level(logging.WARNING, logger="document_lakehouse.ingestion.canon.pipeline"):
        df = canon_pipeline.scrape_canon(max_id=1)

    assert df["id"].tolist() == [0]
    assert fake.calls == [0, 0]
    assert "canon 0 failed" in caplog.text
    assert "502 bad gateway" in caplog.text
    assert df.attrs["failures"] == [{"id": 0, "reason": "error", "error": "502 bad gateway"}]
    # one line per run names what was lost, not just a count
    assert "1 item(s) could not be fetched: canon 0" in caplog.text


def test_the_budget_covers_the_whole_run(monkeypatch):
    def answer_for(number):
        if number == 0:
            return CANON_0
        if number % 2:
            return RuntimeError("flaky")
        return "No results found."

    fake = make_get_canon(answer_for)
    monkeypatch.setattr(canon_pipeline, "get_canon", fake)

    df = canon_pipeline.scrape_canon(max_id=100, max_failures=1)

    # one success, then two misses and the run stops
    assert df["id"].tolist() == [0]
    assert fake.calls == [0, 1, 1]
