"""CONFIRMED against two real full examples (JSONbored/loopover#9978,
lusky3/Flow-Theme-for-transfer.sh#201) -- Codecov's real Bundle Analysis
comment has an explicit overall-summary sentence, distinct from its
per-asset breakdown table:

    Changes will increase total bundle size by 387.88kB (100.0%) :arrow_up:...
    Changes will decrease total bundle size by 1.98kB (-0.02%) :arrow_down:...
    Bundle size has no change :white_check_mark:

An earlier version of this parser grabbed the FIRST percentage anywhere
after the `[Bundle]` heading, which is wrong when the comment also lists
per-NEW-asset rows (each new asset is always reported as a flat "100.0%"
relative to its own zero baseline, unrelated to the overall delta) --
confirmed live: `loopover#9978`'s real headline says "Bundle size has no
change", but the old regex grabbed an unrelated per-asset "100.0%" row
instead. Anchoring on the explicit "total bundle size" sentence (or the
no-change sentence) fixes this.
"""

from __future__ import annotations

import re

NAME = "codecov_bundle_analysis"

_TOTAL_CHANGE_RE = re.compile(
    r"total bundle size by [\d.]+\s*\w*B\s*\(([+-]?[\d.]+)%\)"
)
_NO_CHANGE_RE = re.compile(r"bundle size has no change", re.I)


def detect(actor: str, body: str) -> bool:
    return actor == "codecov[bot]" and "[bundle]" in body.lower()


def parse(body: str) -> dict | None:
    if _NO_CHANGE_RE.search(body):
        return {"bundle_size_delta_pct": 0.0}
    m = _TOTAL_CHANGE_RE.search(body)
    if not m:
        return None  # unrecognized sub-format -- fail closed to Tier B, don't guess
    value = float(m.group(1))
    if "decrease" in body[max(0, m.start() - 30):m.start()].lower():
        value = -abs(value)
    return {"bundle_size_delta_pct": value}
