"""NOT confirmed against real GH Archive data in this session. WebPageTest's
GitHub Action reportedly reports LCP/TBT/CLS directly by metric name rather
than a Lighthouse score, per general knowledge -- but the exact comment shape
wasn't observed live. Same "never claim Tier A on a guess" policy as the
other unverified templates.
"""

from __future__ import annotations

NAME = "webpagetest"


def detect(actor: str, body: str) -> bool:
    b = body.lower()
    return "webpagetest" in actor.lower() or "webpagetest" in b


def parse(body: str) -> dict | None:
    return None  # unverified format -- never claim Tier A, see module docstring
