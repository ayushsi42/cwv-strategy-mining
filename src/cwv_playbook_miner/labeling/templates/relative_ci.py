"""CONFIRMED against real GH Archive data (2026-08-11, weareinreach/InReach):

    ## [#3255](...) Bundle Size — 3.6MiB (~-0.01%).
    81c6e65(current) vs 412cd85 **[dev#3253](...)**(baseline)

RelativeCI's real bundle-size-delta comment. Bundle size, not a Lighthouse
performance score -- stored under `bundle_size_delta_pct` (lower is better,
opposite direction from `performance`; see HIGHER_IS_BETTER in signal_label.py).
"""

from __future__ import annotations

import re

NAME = "relative_ci"

_DELTA_RE = re.compile(r"Bundle Size\s*[—-]\s*[\d.]+\s*\w*i?B\s*\(~([+-]?[\d.]+)%\)")


def detect(actor: str, body: str) -> bool:
    return actor == "relativeci[bot]" or "relative-ci.com" in body.lower()


def parse(body: str) -> dict | None:
    m = _DELTA_RE.search(body)
    if not m:
        return None
    return {"bundle_size_delta_pct": float(m.group(1))}
