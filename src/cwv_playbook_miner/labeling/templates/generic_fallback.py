"""Last-resort template: matches anything (so the registry always has a hit
for a comment that already cleared stage 0's marker pre-filter), never
parses a score. This is what keeps a marker-matched-but-unrecognized-tool
comment as Tier B ("flagged") instead of silently dropped -- but per the
false-positive-rate finding in docs/pipeline-design.md, most marker matches
that fall through to this template are noise (codecov coverage reports,
deploy-status bots, etc.), so Tier B volume from here should be treated as
low-confidence and rarely worth a `gh api` spend on its own.
"""

from __future__ import annotations

NAME = "generic_fallback"


def detect(actor: str, body: str) -> bool:
    return True


def parse(body: str) -> dict | None:
    return None
