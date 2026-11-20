"""Make a pipeline's un-fetched rows identifiable after the run.

A pipeline that swallows a failure returns a shorter frame, and once that frame
is written out a corpus that lost three chapters is indistinguishable from a
complete one. Each pipeline therefore records every item it could not fetch as
`frame.attrs["failures"]` and logs one summary line, so the loss is visible
both to code and to a reader of the log.

The report is a list of dicts holding the item's coordinates, the reason and
the last error. `to_csv` does not write frame attributes, so anything that
persists a frame should read `attrs["failures"]` first.
"""

import logging

log = logging.getLogger(__name__)


def attach(frame, failures, describe):
    """Return `frame` with `failures` attached and one summary line logged.

    `describe` turns one failure dict into a short label, so the summary names
    the actual items ("canon 12", "Genesis 3") rather than a bare count.
    """
    frame.attrs["failures"] = list(failures)

    if failures:
        log.warning(
            "%s item(s) could not be fetched: %s",
            len(failures),
            ", ".join(describe(failure) for failure in failures),
        )

    return frame
