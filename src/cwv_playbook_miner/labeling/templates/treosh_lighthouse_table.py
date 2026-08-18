"""CONFIRMED against real GH Archive data (2026-08-12, AgentsKit-io/agentskit):

    ## Lighthouse
    | URL | Performance | Accessibility | Best practices | SEO |
    |---|---|---|---|---|
    | http://127.0.0.1:3000/ | 52 | 92 | 96 | 100 |
    | http://127.0.0.1:3000/docs | 65 | 100 | 96 | 100 |

treosh/lighthouse-ci-action in its inline-table comment mode. Tier A: score
is inline and parseable, no external fetch needed.
"""

from __future__ import annotations

import re

NAME = "treosh_lighthouse_table"

_HEADER_RE = re.compile(r"^\|(.+)\|\s*$", re.M)


def detect(actor: str, body: str) -> bool:
    if not actor.endswith("[bot]"):
        return False
    # Requires the actual "## Lighthouse" heading, not loose keyword
    # co-occurrence -- a looser check false-matched aem-code-sync[bot]'s
    # unrelated-shaped comment in live testing (it mentions "lighthouse" via
    # a scorecalc URL and "performance" via a badge alt-text).
    return bool(re.search(r"^#+\s*lighthouse\b", body, re.I | re.M)) and "|" in body


def parse(body: str) -> dict | None:
    rows = [line for line in body.splitlines() if line.strip().startswith("|")]
    if len(rows) < 2:
        return None

    header_cells = [c.strip().lower() for c in rows[0].strip("|").split("|")]
    if "performance" not in header_cells:
        return None
    perf_idx = header_cells.index("performance")

    scores = []
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) <= perf_idx or set(cells[0]) <= {"-", " "}:
            continue  # header-separator row or malformed
        try:
            scores.append(float(cells[perf_idx]))
        except ValueError:
            continue

    if not scores:
        return None
    return {"performance": sum(scores) / len(scores)}
