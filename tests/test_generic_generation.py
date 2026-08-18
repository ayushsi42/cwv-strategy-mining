from cwv_playbook_miner.generation.render_candidate import validate_candidate_text


def _candidate() -> str:
    return """---
issue_type: reduce-render-work
risk_tier: medium
source_prs: [example/repo#1]
---
# Reduce render work

## What this addresses
Excessive work.

## Evidence
Measured improvement in example/repo#1.

## Recommended approach
Use the source change.

## Risks and limitations
Validate on the target page.

## Anti-pattern evidence
No regression-side evidence was found.
"""


def test_generic_candidate_contract_accepts_grounded_document() -> None:
    assert validate_candidate_text(_candidate(), "reduce-render-work") == []


def test_generic_candidate_contract_requires_sources() -> None:
    text = _candidate().replace("source_prs: [example/repo#1]", "source_prs: []")
    assert "source_prs must contain at least one source PR" in validate_candidate_text(
        text, "reduce-render-work",
    )
