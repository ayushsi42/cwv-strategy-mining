from unittest.mock import patch

from cwv_playbook_miner.classification.classify_cluster import Classification
from cwv_playbook_miner.extraction.cluster import TechniqueCluster
from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.generation.render_candidate import render_candidate, validate_candidate_text


def _candidate() -> str:
    return """---
issue_type: layout-stability--reserve-async-space
parent_strategy: layout-stability
risk_tier: medium
cwv_metrics: [cls]
source_prs: [example/repo#1]
required_validation:
  - async_content_causes_layout_shift
forbidden_techniques: []
---
# Reserve space for asynchronous content

> **Risk tier:** medium · **Parent strategy:** Layout stability · **CWV metric:** CLS

## What this addresses
Late content insertion can move visible content.

## When to apply / when to skip
**Apply when:**
- A measured async panel shifts surrounding content.

**Skip when:**
- The panel is outside the viewport.

## Required validation
Confirm `async_content_causes_layout_shift` using the measured page.

## Recommended approaches
```html
<!-- Good -->
<section class="reserved-slot"></section>
```

## Anti-patterns
No evidence-grounded code anti-pattern was available.

## How to verify
Compare CLS before and after under the same conditions.

## Evidence and confidence
Observed in `example/repo#1`; transferability remains an inference.

## Risks and limitations
Do not reserve substantially more space than the loaded content needs.
"""


def test_generic_candidate_contract_accepts_grounded_document() -> None:
    assert validate_candidate_text(_candidate(), "layout-stability--reserve-async-space") == []


def test_generic_candidate_contract_requires_sources() -> None:
    text = _candidate().replace("source_prs: [example/repo#1]", "source_prs: []")
    assert "source_prs must contain at least one source PR" in validate_candidate_text(
        text, "layout-stability--reserve-async-space",
    )


def test_platform_flavor_fields_are_rejected() -> None:
    text = _candidate().replace("risk_tier: medium", "applicable_flavors: [eds]\nrisk_tier: medium", 1)
    assert "platform flavor fields are forbidden" in validate_candidate_text(
        text, "layout-stability--reserve-async-space",
    )


def test_invalid_forbidden_regex_is_rejected() -> None:
    text = _candidate().replace(
        "forbidden_techniques: []",
        "forbidden_techniques:\n  - pattern: '[invalid'\n    reason: bad regex",
    )
    assert any("invalid regex" in problem for problem in validate_candidate_text(
        text, "layout-stability--reserve-async-space",
    ))


def test_generation_uses_draft_and_critic_calls() -> None:
    cluster = TechniqueCluster(
        technique="reserve async space", normalized_key="layout-stability--reserve-async-space",
        parent_strategy="layout-stability", frequency=3, avg_delta=10,
        framework_hints=["any"], applicable_signals=["CLS"], why_it_works="prevents shifts",
        example_code_patterns=["reserve a slot"], example_problem_symptoms=["late shift"],
        source_pr_ids=["example/repo#1"], distinct_repo_count=2, positive_count=3,
        directional_consistency=1.0, confidence="medium", cwv_metrics=["cls"],
    )
    classification = Classification(
        normalized_key=cluster.normalized_key, technique=cluster.technique,
        action="candidate", target_issue_type=cluster.normalized_key,
        action_reason="supported", risk_tier_guess="medium",
    )
    record = PRRecord(
        id="example/repo#1", repo="example/repo", pr_number=1,
        signal_type="perf_improvement", metric_key="cls", before=0.2, after=0.1,
        delta=-0.1, changed_files=[],
    )
    with patch(
        "cwv_playbook_miner.generation.render_candidate.complete_text",
        side_effect=[_candidate(), _candidate().replace("Reserve space", "Critiqued: reserve space", 1)],
    ) as completion:
        result = render_candidate(cluster, classification, [], [record], "openai", "test", 30)

    assert completion.call_count == 2
    assert "Critiqued: reserve space" in result
