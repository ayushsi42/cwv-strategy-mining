"""Render evidence-grounded, platform-neutral CWV child playbooks."""

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
    "When to apply / when to skip",
    "Required validation",
    "Recommended approaches",
    "Anti-patterns",
    "How to verify",
    "Evidence and confidence",
    "Risks and limitations",
)

DRAFT_SYSTEM_PROMPT = """You author a production-quality, platform-neutral Core Web Vitals playbook for ONE evidence-qualified child strategy. The quality bar is an expert engineering runbook, not a PR summary.

Use only mechanisms, applicability conditions, code shapes, risks, and measurements supported by the supplied evidence. Do not invent universal percentages, browser-support numbers, APIs, validation rules, or bad patterns. Generalize repository/framework names only when the evidence supports the same mechanism across sources. Never add CMS, delivery-flavor, AEM, EDS, CS, AMS, or product-specific translation.

Output only one Markdown document with this exact contract:
---
issue_type: <stable child id>
parent_strategy: <stable parent id>
risk_tier: <low|medium|high>
cwv_metrics: [<measured metrics>]
source_prs: [<repo#number>, ...]
required_validation:
  - <snake_case precondition grounded in evidence>
forbidden_techniques:
  - pattern: '<simple safe Python regex>'
    reason: "<evidence-grounded rejection reason>"
---
# <specific child strategy title>

> **Risk tier:** ... · **Parent strategy:** ... · **CWV metric:** ...

## What this addresses
## When to apply / when to skip
Include explicit **Apply when:** and **Skip when:** lists.
## Required validation
Explain every front-matter validation ID and what evidence must be observed.
## Recommended approaches
Include at least one concrete fenced example marked Good, faithfully generalized from supplied patches.
## Anti-patterns
Include a concrete fenced example marked Bad and **Why this is bad:** only when supported by a pre-change patch or regression evidence. If no defensible code anti-pattern exists, say the evidence is insufficient and use forbidden_techniques: [].
## How to verify
Describe before/after measurement using only supplied metrics; do not promise a fixed improvement.
## Evidence and confidence
Separate observed facts from inference and cite every source PR.
## Risks and limitations

Prefer precise conditional guidance. A recommendation-only outcome is better than an unsafe guessed edit."""

CRITIC_SYSTEM_PROMPT = """You are the final technical editor for a platform-neutral CWV playbook. Rewrite the supplied draft into a publication-quality document while preserving its issue_type and evidence.

Reject and remove: mixed mechanisms, unsupported claims, fabricated code, generic filler, framework-specific claims presented as universal, unsafe regexes, and any CMS/AEM/delivery-flavor content. Ensure Apply/Skip gates are operational, every validation ID is explained, Good/Bad examples are evidence-derived, verification is measurable, and evidence is clearly separated from inference. If evidence cannot justify an anti-pattern regex, use an empty forbidden_techniques list. Output only the complete revised Markdown document with no commentary."""


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
    ) or "No matched regression PR evidence was found. Do not fabricate one."
    return f"""Stable identity:
issue_type: {classification.target_issue_type}
parent_strategy: {cluster.parent_strategy}
risk_tier: {classification.risk_tier_guess}
measured_metrics: {', '.join(cluster.cwv_metrics)}

Child strategy summary:
name: {cluster.technique}
mechanism: {cluster.why_it_works}
signals: {', '.join(cluster.applicable_signals)}
aliases: {', '.join(cluster.aliases)}
statistical support: {cluster.frequency} observations across {cluster.distinct_repo_count} repositories
directional consistency: {cluster.directional_consistency:.1%} ({cluster.positive_count} improvements, {cluster.negative_count} regressions)
absolute measured-delta summary: p25={cluster.delta_p25}, median={cluster.avg_delta}, p75={cluster.delta_p75}
confidence: {cluster.confidence}

Raw improvement evidence:
{_source_block(source_records)}

Regression evidence:
{regression_evidence}
"""


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
    evidence_prompt = build_prompt(cluster, classification, antipatterns, source_records)
    draft = _extract_markdown_document(
        complete_text(DRAFT_SYSTEM_PROMPT, evidence_prompt, backend=backend, model=model, timeout=timeout)
    )
    critic_prompt = f"""Evidence packet:
{evidence_prompt}

Draft to audit and rewrite:
{draft}
"""
    return _extract_markdown_document(
        complete_text(CRITIC_SYSTEM_PROMPT, critic_prompt, backend=backend, model=model, timeout=timeout)
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
        problems.append(f"issue_type {frontmatter.get('issue_type')!r} != expected {expected_issue_type!r}")
    if not frontmatter.get("parent_strategy"):
        problems.append("parent_strategy is required")
    if frontmatter.get("risk_tier") not in {"low", "medium", "high"}:
        problems.append("risk_tier must be low, medium, or high")
    if not isinstance(frontmatter.get("cwv_metrics"), list) or not frontmatter["cwv_metrics"]:
        problems.append("cwv_metrics must be a non-empty list")
    if not frontmatter.get("source_prs"):
        problems.append("source_prs must contain at least one source PR")
    validations = frontmatter.get("required_validation")
    if not isinstance(validations, list) or not validations:
        problems.append("required_validation must be a non-empty list")
    elif any(not re.fullmatch(r"[a-z0-9_]+", str(item)) for item in validations):
        problems.append("required_validation IDs must be snake_case")
    forbidden = frontmatter.get("forbidden_techniques")
    if not isinstance(forbidden, list):
        problems.append("forbidden_techniques must be a list")
    else:
        for index, rule in enumerate(forbidden):
            if not isinstance(rule, dict) or not rule.get("pattern") or not rule.get("reason"):
                problems.append(f"forbidden_techniques[{index}] requires pattern and reason")
                continue
            try:
                re.compile(rule["pattern"])
            except re.error as exc:
                problems.append(f"forbidden_techniques[{index}] invalid regex: {exc}")
            if re.search(r"\([^)]*[+*][^)]*\)[+*]", rule["pattern"]):
                problems.append(f"forbidden_techniques[{index}] may catastrophically backtrack")
    if "applicable_flavors" in frontmatter or "flavor_overrides" in frontmatter:
        problems.append("platform flavor fields are forbidden")

    positions = []
    for section in REQUIRED_SECTIONS:
        match = re.search(rf"^## {re.escape(section)}$", body, re.M)
        if not match:
            problems.append(f"missing required section {section!r}")
        else:
            positions.append(match.start())
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        problems.append("required sections are out of order")
    if "**Apply when:**" not in body or "**Skip when:**" not in body:
        problems.append("Apply when and Skip when gates are required")
    if not re.search(r"```[a-zA-Z0-9_-]*\n[\s\S]*?\bGood\b", body):
        problems.append("at least one fenced Good example is required")
    anti_section = body.split("## Anti-patterns", 1)[-1].split("## How to verify", 1)[0]
    if forbidden and ("Bad" not in anti_section or "**Why this is bad:**" not in anti_section):
        problems.append("forbidden techniques require a Bad example and explanation")
    return problems


def write_candidate(text: str, issue_type: str, candidates_dir: Path) -> Path:
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{issue_type}.md"
    path.write_text(text, encoding="utf-8")
    return path
