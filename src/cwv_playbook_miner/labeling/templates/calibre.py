"""NOT confirmed against real GH Archive data in this session. Calibre
(calibreapp) is a known GitHub App reporting performance-budget results, but
its exact comment shape (if it comments on PRs at all vs. only using Checks)
wasn't observed live. Same "never claim Tier A on a guess" policy as
lighthouse_check_action.py.
"""

from __future__ import annotations

NAME = "calibre"


def detect(actor: str, body: str) -> bool:
    b = body.lower()
    return "calibre" in actor.lower() or ("calibre" in b and "budget" in b)


def parse(body: str) -> dict | None:
    return None  # unverified format -- never claim Tier A, see module docstring
