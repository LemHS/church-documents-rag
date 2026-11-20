"""Summa Theologiae scraping, driven by an explicit query object.

The notebook passed seven positional arguments and rebuilt the session on every
call; this module names the parameters in `SummaQuery` and keeps the session on
the client so a run reuses one connection and one set of headers.
"""

from dataclasses import dataclass

import requests

from ..fetch import call


@dataclass(frozen=True)
class SummaQuery:
    """One window of the Summa, and which aquinas.cc cells to read for it.

    A part is either a whole part ("I", "III") or a part of a part
    ("I" of "II" is I-II, "II" of "II" is II-II). The three `did_*` ids are
    aquinas.cc's internal handles for the hierarchy, Latin and English cell
    trees; they differ per part.
    """

    part: str
    part_of_part: str | None = None
    start: int = 0
    length: int = 36
    did_hierarchy: int = -15
    did_lang1: int = 56
    did_lang2: int = 57

    @property
    def url(self):
        if self.part_of_part is None:
            return f"https://aquinas.cc/la/en/~ST.{self.part}"
        return f"https://aquinas.cc/la/en/~ST.{self.part_of_part}-{self.part}"


class SummaTheologiae:
    """Reads hierarchy, Latin and English cells from the aquinas.cc API."""

    api_url = "https://aquinas.cc/api/data/getCells"

    def __init__(self, session=None):
        self.session = session if session is not None else requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def fetch(self, query):
        """Return `(url, hierarchy, latin, english)` for one window.

        Each response is aquinas.cc's `[total, [[cell_id, text], ...]]` list;
        the window is empty (`[..., []]`) once `start` is past the end.
        """
        self.session.headers["Referer"] = query.url

        bodies = []
        for did in (query.did_hierarchy, query.did_lang1, query.did_lang2):
            response = call(
                lambda did=did: self._post(query, did),
                url=query.url,
            )
            bodies.append(response.json())

        hierarchy, latin, english = bodies
        return query.url, hierarchy, latin, english

    def _post(self, query, did):
        payload = {
            "did": did,
            "start": query.start,
            "len": query.length,
        }
        return self.session.post(self.api_url, json=payload, timeout=30)
