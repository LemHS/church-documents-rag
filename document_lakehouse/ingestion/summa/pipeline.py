"""End-to-end Summa Theologiae scrape: every part, one window at a time."""

import logging

import pandas as pd

from ..failures import attach
from .scraper import SummaQuery, SummaTheologiae

log = logging.getLogger(__name__)

# each part is (part,) or (part_of_part, part); a part is fetched until the
# hierarchy window comes back empty
PARTIS = (("I",), ("I",), ("I", "II"), ("II", "II"), ("III",), ("III",))

DID = {
    ## every part have a did combination
    "did_hierarchy": (-15, -16, -17, -18, -19, -20),
    "did_lang1": (56, 60, 64, 68, 72, 76),
    "did_lang2": (57, 61, 65, 69, 73, 77),
}


def scrape_summa(partis=PARTIS, did=DID, length=20, max_failures=5, max_windows=None):
    """Scrape the hierarchy, latin and english cell texts of every part.

    `max_windows` stops after that many windows in total — for smoke runs, not
    for a full dataset. A window that fails and is fetched again is recorded in
    `frame.attrs["failures"]`, marked `recovered` once that window comes back.
    """
    dct = {
        "hierarchy": [],
        "latin": [],
        "eng": []
    }

    failures = []
    start = 0
    tries = 0
    start_i = 0
    windows = 0

    summa = SummaTheologiae()

    for i, parti in enumerate(partis, start=start_i):
        next_part = False
        while not next_part:
            if max_windows is not None and windows >= max_windows:
                break

            if len(parti) == 1:
                part = parti[0]
                part_of_part = None
            else:
                part_of_part, part = parti
            try:

                query = SummaQuery(
                    part=part,
                    part_of_part=part_of_part,
                    start=start,
                    length=length,
                    did_hierarchy=did["did_hierarchy"][i],
                    did_lang1=did["did_lang1"][i],
                    did_lang2=did["did_lang2"][i],
                )
                url, summa_t_hierarchy, summa_t_latin, summa_t_eng = summa.fetch(query)

                for failure in failures:
                    if (failure["part"], failure["part_of_part"], failure["start"]) == (part, part_of_part, start):
                        failure["recovered"] = True

                start += length
                windows += 1

                dct["hierarchy"] += list(map(lambda x: x[1], summa_t_hierarchy[1]))
                dct["latin"] += list(map(lambda x: x[1], summa_t_latin[1]))
                dct["eng"] += list(map(lambda x: x[1], summa_t_eng[1]))

                if len(summa_t_hierarchy[1]) == 0:
                    start = 0
                    next_part = True

            except Exception as e:
                failures.append({"part": part, "part_of_part": part_of_part, "start": start, "reason": "error", "error": str(e), "recovered": False})
                if tries > max_failures:
                    start_i = i
                    raise
                else:
                    log.warning("%s window at %s failed (%s/%s): %s", part, start, tries + 1, max_failures, e)
                tries += 1
                continue

    return attach(
        pd.DataFrame(dct),
        failures,
        lambda failure: f"{failure['part']}{'-' + failure['part_of_part'] if failure['part_of_part'] else ''} at {failure['start']}",
    )
