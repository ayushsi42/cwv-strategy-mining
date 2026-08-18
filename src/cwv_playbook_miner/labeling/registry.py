"""Fingerprint-first template matching. Per the plan's live-verified finding
(109 marker-matched comments across 50 real hours -> 60 were plain
`codecov[bot]` coverage-report noise, several other bots 100% noise), a
marker-keyword match on its own is not a reliable gate. This registry tries
each known tool's `detect()` in order -- specific/confirmed templates first,
`generic_fallback` last -- so only a real structural fingerprint gets you
past "flagged," and only a *parseable* one gets you to Tier A.
"""

from __future__ import annotations

from cwv_playbook_miner.labeling.templates import (
    aem_code_sync,
    bundle_size_table,
    calibre,
    codecov_bundle_analysis,
    generic_fallback,
    lighthouse_check_action,
    netlify_lighthouse,
    relative_ci,
    treosh_lighthouse_reports,
    treosh_lighthouse_table,
    webpagetest,
)

# Order matters: most-specific fingerprint first (exact marker strings /
# specific bot logins), looser structural checks after, generic_fallback
# always last. Live testing caught a real ordering bug -- aem_code_sync's
# exact `<!-- aem-bot-psi -->` marker must be tried before
# treosh_lighthouse_table's looser heading check, since aem-code-sync's body
# also happens to contain the words "lighthouse" and "performance".
TEMPLATES = [
    aem_code_sync,
    treosh_lighthouse_reports,
    treosh_lighthouse_table,
    netlify_lighthouse,
    relative_ci,
    bundle_size_table,
    codecov_bundle_analysis,
    lighthouse_check_action,
    calibre,
    webpagetest,
    generic_fallback,
]


def match_template(actor: str, body: str):
    for template in TEMPLATES:
        if template.detect(actor, body):
            return template
    return None  # unreachable -- generic_fallback.detect() always returns True
