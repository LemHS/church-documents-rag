"""Unit tests for the failure report the pipelines attach to their frames."""

import logging

import pandas as pd

from document_lakehouse.ingestion.failures import attach


def test_failures_are_attached_to_the_frame():
    frame = pd.DataFrame({"id": [0, 1]})

    result = attach(frame, [{"id": 7, "reason": "error", "error": "boom"}], lambda failure: f"canon {failure['id']}")

    assert result is frame
    assert frame.attrs["failures"] == [{"id": 7, "reason": "error", "error": "boom"}]


def test_a_clean_run_attaches_an_empty_report_and_says_nothing(caplog):
    frame = pd.DataFrame({"id": [0]})

    with caplog.at_level(logging.WARNING, logger="document_lakehouse.ingestion.failures"):
        attach(frame, [], lambda failure: "unused")

    assert frame.attrs["failures"] == []
    assert caplog.text == ""


def test_the_summary_names_the_items(caplog):
    frame = pd.DataFrame({"id": [0]})
    failures = [
        {"id": 3, "reason": "error", "error": "boom"},
        {"id": 4, "reason": "no results", "error": ""},
    ]

    with caplog.at_level(logging.WARNING, logger="document_lakehouse.ingestion.failures"):
        attach(frame, failures, lambda failure: f"canon {failure['id']}")

    assert "2 item(s) could not be fetched: canon 3, canon 4" in caplog.text


def test_the_report_is_a_copy_of_what_was_passed():
    frame = pd.DataFrame()
    failures = [{"id": 1}]

    attach(frame, failures, lambda failure: "x")
    failures.append({"id": 2})

    assert frame.attrs["failures"] == [{"id": 1}]
