"""CONFIRMED against real GH Archive data (2026-08-13, mui/mui-x via
`code-infra-dashboard[bot]`):

    ## Bundle size
    | Bundle | Parsed size | Gzip size |
    |:----------|----------:|----------:|
    | @mui/x-data-grid |  0B<sup>(0.00%)</sup> |  0B<sup>(0.00%)</sup> |

A shared "bundle size table" shape -- likely reused by other size-limit-style
bots beyond this one actor, hence detected structurally (heading + table
shape) rather than by a specific bot login.
"""

from __future__ import annotations

import re

NAME = "bundle_size_table"

_PCT_RE = re.compile(r"\(([+-]?[\d.]+)%\)")


def detect(actor: str, body: str) -> bool:
    return "## bundle size" in body.lower() and "gzip size" in body.lower()


def parse(body: str) -> dict | None:
    rows = [line for line in body.splitlines() if line.strip().startswith("|")]
    deltas = [float(m) for row in rows for m in _PCT_RE.findall(row)]
    if not deltas:
        return None
    return {"bundle_size_delta_pct": sum(deltas) / len(deltas)}
