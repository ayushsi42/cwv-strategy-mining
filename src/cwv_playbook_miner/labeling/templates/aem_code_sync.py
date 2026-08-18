"""CONFIRMED against real GH Archive data (2026-08-12, kawaind/bimota):

    <!-- aem-bot-psi -->
    | | Page | Scores | Audits | Google |
    |-|------|--------|--------|--------|
    | :iphone: | [/](https://...aem.live/) | [![PERFORMANCE](https://img.shields.io/badge/PERFORMANCE-98-green...)]
    (https://googlechrome.github.io/lighthouse/scorecalc/#device=mobile&version=13.4.1&SI=3857.25...&FCP=1142&LCP=1501&TBT=0&CLS=0 "See Calculator") ...

This is only an input-format parser for a real Lighthouse-reporting bot. The
scorecalc link's query string carries raw CWV metric values (FCP/LCP/TBT/CLS
in ms, SI in ms), not just a 0-100 score. It has no role in candidate
normalization, grounding, classification, or generation.
"""

from __future__ import annotations

import re

NAME = "aem_code_sync"

_MARKER = "<!-- aem-bot-psi -->"
_BADGE_RE = re.compile(r"PERFORMANCE-(\d+)-", re.I)
_SCORECALC_RE = re.compile(r"scorecalc/#([^\s\"]+)")


def detect(actor: str, body: str) -> bool:
    return actor.endswith("[bot]") and _MARKER in body


def parse(body: str) -> dict | None:
    metrics: dict[str, float] = {}

    badge_match = _BADGE_RE.search(body)
    if badge_match:
        metrics["performance"] = float(badge_match.group(1))

    scorecalc_match = _SCORECALC_RE.search(body)
    if scorecalc_match:
        query = scorecalc_match.group(1)
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        for key, out_key in (("FCP", "fcp_ms"), ("LCP", "lcp_ms"), ("TBT", "tbt_ms"),
                              ("CLS", "cls"), ("SI", "si_ms")):
            if key in params:
                try:
                    metrics[out_key] = float(params[key])
                except ValueError:
                    continue

    return metrics or None
