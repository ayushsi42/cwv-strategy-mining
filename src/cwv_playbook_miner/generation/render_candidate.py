"""Stage 6: render platform-neutral, evidence-grounded CWV candidates."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cwv_playbook_miner.antipatterns.pull_antipatterns import AntiPatternMatch
from cwv_playbook_miner.classification.classify_cluster import Classification
from cwv_playbook_miner.extraction.cluster import TechniqueCluster
from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import complete_text


REQUIRED_SECTIONS = (
    "What this addresses",
    "Evidence",
    "Recommended approach",
    "Risks and limitations",
    "Anti-pattern evidence",
)


SYSTEM_PROMPT = """You write platform-neutral Core Web Vitals technique candidates from real pull-request evidence.

Output only one Markdown document. Do not mention or translate to any CMS, delivery flavor, or framework unless that technology appears in the source PR itself. Do not invent code, validation rules, mechanisms, or anti-patterns.

The document must use this structure:
---
issue_type: <kebab-case slug>
risk_tier: <low|medium|high>
source_prs: [<repo#number>, ...]
---
# <title>

## What this addresses
## Evidence
## Recommended approach
## Risks and limitations
## Anti-pattern evidence

Use short source excerpts or faithful pseudocode only when directly supported by a supplied patch. If regression evidence is absent, say so explicitly in the Anti-pattern evidence section."""


def _source_block(records: list[PRRecord]) -> str:
    blocks = []
    for record in records:
        files = []
        for changed_file in record.changed_files[:8]:
            patch = changed_file.get("patch", "")
            files.append(f"File: {changed_file.get('filename', '')}\n{patch[:6000]}")
        blocks.append(
            f"Source: {record.id}\nTitle: {record.title or '(unavailable)'}\n"
            f"Measured: {record.metric_key} {record.before} -> {record.after} (delta {record.delta})\n"
            f"PR body: {(record.pr_body_markdown or '(unavailable)')[:3000]}\n"
            f"Changed files:\n{chr(10).join(files)}"
        )
    return "\n\n".join(blocks)


def build_prompt(
    cluster: TechniqueCluster,
    classification: Classification,
    antipatterns: list[AntiPatternMatch],
    source_records: list[PRRecord],
) -> str:
    regression_evidence = "\n\n".join(
        f"Source: {match.source_id}\nTechnique: {match.technique}\n"
        f"Problem: {match.problem_symptom}\nCode pattern: {match.code_pattern}\n"
        f"Explanation: {match.why_it_works}"
        for match in antipatterns
    ) or "No matched regression PR evidence was found. State this; do not fill the gap from general knowledge."

    return f"""Classification:
issue_type: {classification.target_issue_type}
risk_tier: {classification.risk_tier_guess}
reason: {classification.action_reason}

Extracted cluster summary (secondary evidence; prefer the raw source below):
technique: {cluster.technique}
why_it_works: {cluster.why_it_works}
signals: {', '.join(cluster.applicable_signals)}
source_prs: {', '.join(cluster.source_pr_ids)}
statistical support: {cluster.frequency} observations across {cluster.distinct_repo_count} repositories
directional consistency: {cluster.directional_consistency:.1%} ({cluster.positive_count} improvements, {cluster.negative_count} regressions)
absolute delta distribution: p25={cluster.delta_p25}, median={cluster.avg_delta}, p75={cluster.delta_p75}
confidence: {cluster.confidence}
known aliases: {', '.join(cluster.aliases)}

Raw improvement-side source PR evidence:
{_source_block(source_records)}

Regression-side evidence:
{regression_evidence}

Write the candidate without adding platform-specific context absent from these sources."""


def _extract_markdown_document(text: str) -> str:
    fence = re.search(r"```(?:markdown)?\n(.*?)\n```", text, re.S)
    if fence and fence.group(1).strip().startswith("---"):
        return fence.group(1).strip()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[index:]).strip()
    return text.strip()


def render_candidate(
    cluster: TechniqueCluster,
    classification: Classification,
    antipatterns: list[AntiPatternMatch],
    source_records: list[PRRecord],
    backend: str,
    model: str | None,
    timeout: int,
) -> str:
    prompt = build_prompt(cluster, classification, antipatterns, source_records)
    return _extract_markdown_document(
        complete_text(SYSTEM_PROMPT, prompt, backend=backend, model=model, timeout=timeout)
    )


def _split_document(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise ValueError("document does not contain YAML front matter")
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def validate_candidate_text(text: str, expected_issue_type: str) -> list[str]:
    problems = []
    try:
        frontmatter, body = _split_document(text)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    if frontmatter.get("issue_type") != expected_issue_type:
        problems.append(
            f"issue_type {frontmatter.get('issue_type')!r} != expected {expected_issue_type!r}"
        )
    if frontmatter.get("risk_tier") not in {"low", "medium", "high"}:
        problems.append("risk_tier must be low, medium, or high")
    if not frontmatter.get("source_prs"):
        problems.append("source_prs must contain at least one source PR")
    headings = set(re.findall(r"^## (.+)$", body, re.M))
    for section in REQUIRED_SECTIONS:
        if section not in headings:
            problems.append(f"missing required section {section!r}")
    return problems


def write_candidate(text: str, issue_type: str, candidates_dir: Path) -> Path:
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{issue_type}.md"
    path.write_text(text, encoding="utf-8")
    return path
