"""CONFIRMED against real GH Archive data (2026-08-10, chucknmore2-ops/joshuafink-website):

    ## 🔦 Lighthouse CI
    **Reports:** {"http://localhost:3000/":"https://storage.googleapis.com/.../report.html", ...}

treosh/lighthouse-ci-action's report-link mode -- no inline score, only links
to hosted reports. Same tool as treosh_lighthouse_table.py, different config.
Recognized (Tier B: flagged, real tool) but never Tier A -- parse() always
returns None by design, since getting a score would need an extra fetch of
the linked report, defeating the point of free labeling.
"""

from __future__ import annotations

NAME = "treosh_lighthouse_reports"


def detect(actor: str, body: str) -> bool:
    if not actor.endswith("[bot]"):
        return False
    return "lighthouse ci" in body.lower() and "**reports:**" in body.lower()


def parse(body: str) -> dict | None:
    return None  # Tier B by design -- see module docstring
