"""NOT confirmed against real GH Archive data in this session -- no sample
turned up in the ~50-hour live scan. `foo-software/lighthouse-check-action`
is a known tool (badge/table PR comments), but detect()/parse() below are
best-effort from general knowledge only, not verified structure. Treat as
Tier B (flagged, unparseable) until a real sample confirms the shape --
parse() deliberately always returns None so this can never silently produce
a wrong Tier-A delta.
"""

from __future__ import annotations

NAME = "lighthouse_check_action"


def detect(actor: str, body: str) -> bool:
    b = body.lower()
    return actor.endswith("[bot]") and "lighthouse check" in b


def parse(body: str) -> dict | None:
    return None  # unverified format -- never claim Tier A, see module docstring
