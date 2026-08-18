"""CONFIRMED against real GH Archive data (2026-08-11,
apikujuni-source/the-gleaning-ground) -- found while inspecting a full body
to check why `netlify[bot]` kept showing up as noise in earlier sweeps.
Netlify's own Lighthouse plugin (when enabled on a repo) appends a real
score to its deploy-preview comment, bold-label style rather than a table:

    |<...>Lighthouse | 1 paths audited<br />**Performance**: 91<br />**Accessibility**: 98<br />...

This is a genuinely different, previously-missed real source -- most
`netlify[bot]` comments are pure deploy-status noise (no Lighthouse plugin),
but the ones that do carry this block are real Tier A signal.
"""

from __future__ import annotations

import re

NAME = "netlify_lighthouse"

_PERF_RE = re.compile(r"\*\*Performance\*\*:\s*(\d+)")


def detect(actor: str, body: str) -> bool:
    return actor == "netlify[bot]" and "lighthouse" in body.lower() and "**performance**:" in body.lower()


def parse(body: str) -> dict | None:
    m = _PERF_RE.search(body)
    if not m:
        return None
    return {"performance": float(m.group(1))}
