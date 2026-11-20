"""Unit tests for the summa client, pinned to recorded aquinas.cc responses.

`fixtures/summa_I_start_0_post20.json` holds the three responses (hierarchy,
Latin, English) for ST I, start 0, len 20, together with the payloads and
Referer that produced them.
"""

import json
from pathlib import Path

import pytest
import requests

from document_lakehouse.ingestion import fetch
from document_lakehouse.ingestion.summa.scraper import SummaQuery, SummaTheologiae

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.status_checks = 0

    def raise_for_status(self):
        self.status_checks += 1

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.posts = []
        self.sent = []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        response = FakeResponse(self.responses.pop(0))
        self.sent.append(response)
        return response


@pytest.fixture
def recording():
    with open(FIXTURES / "summa_I_start_0_post20.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_fetch_replays_the_recorded_posts(recording):
    session = FakeSession(recording["responses"])

    url, hierarchy, latin, english = SummaTheologiae(session=session).fetch(
        SummaQuery(part="I", start=0, length=20)
    )

    assert url == recording["referer"]
    assert session.posts == [
        {"url": recording["url"], "json": payload, "timeout": 30}
        for payload in recording["payloads"]
    ]
    assert (hierarchy, latin, english) == tuple(recording["responses"])
    assert len(hierarchy[1]) == len(latin[1]) == len(english[1]) == 20


def test_url_is_built_from_the_part():
    assert SummaQuery(part="I").url == "https://aquinas.cc/la/en/~ST.I"
    assert SummaQuery(part="II", part_of_part="I").url == "https://aquinas.cc/la/en/~ST.I-II"
    assert SummaQuery(part="II", part_of_part="II").url == "https://aquinas.cc/la/en/~ST.II-II"
    assert SummaQuery(part="III").url == "https://aquinas.cc/la/en/~ST.III"


def test_defaults_are_the_ones_the_notebook_passed():
    query = SummaQuery(part="I")

    assert (query.start, query.length) == (0, 36)
    assert (query.did_hierarchy, query.did_lang1, query.did_lang2) == (-15, 56, 57)


def test_referer_follows_each_query(recording):
    session = FakeSession(recording["responses"] * 2)
    client = SummaTheologiae(session=session)

    client.fetch(SummaQuery(part="I", start=0, length=20))
    assert session.headers["Referer"] == "https://aquinas.cc/la/en/~ST.I"

    client.fetch(SummaQuery(part="II", part_of_part="I", start=0, length=20))
    assert session.headers["Referer"] == "https://aquinas.cc/la/en/~ST.I-II"
    assert [post["json"]["did"] for post in session.posts] == [-15, 56, 57] * 2


def test_window_is_sent_as_start_and_len(recording):
    session = FakeSession(recording["responses"])

    SummaTheologiae(session=session).fetch(
        SummaQuery(part="I", start=40, length=10, did_hierarchy=-16, did_lang1=60, did_lang2=61)
    )

    assert [post["json"] for post in session.posts] == [
        {"did": -16, "start": 40, "len": 10},
        {"did": 60, "start": 40, "len": 10},
        {"did": 61, "start": 40, "len": 10},
    ]


def test_a_failing_post_is_retried_before_the_next_one_is_sent(recording, monkeypatch):
    monkeypatch.setattr("document_lakehouse.ingestion.fetch.time.sleep", lambda _: None)
    session = FakeSession(recording["responses"])
    bodies = dict(zip((-15, 56, 57), recording["responses"]))
    attempts = {"n": 0}
    sent = []

    class Flaky(FakeResponse):
        def raise_for_status(self):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise requests.ConnectionError("reset")

    def post(url, json=None, timeout=None):
        sent.append(json["did"])
        body = bodies[json["did"]]
        # only the middle (latin) request misbehaves
        return Flaky(body) if json["did"] == 56 else FakeResponse(body)

    session.post = post

    url, hierarchy, latin, english = SummaTheologiae(session=session).fetch(
        SummaQuery(part="I", start=0, length=20)
    )

    assert latin == recording["responses"][1]
    assert sent == [-15, 56, 56, 56, 57]


def test_giving_up_names_the_summa_url(recording, monkeypatch):
    monkeypatch.setattr("document_lakehouse.ingestion.fetch.time.sleep", lambda _: None)
    session = FakeSession(recording["responses"])

    class Broken(FakeResponse):
        def raise_for_status(self):
            raise requests.HTTPError("500", response=type("R", (), {"status_code": 500})())

    session.post = lambda url, json=None, timeout=None: Broken(None)

    with pytest.raises(fetch.RetryError, match="~ST.I"):
        SummaTheologiae(session=session).fetch(SummaQuery(part="I", length=20))
