"""Stage 3: generate AEM-format playbook files.

Two generation modes:
  render_new_playbook   — full {issue_type}.md for a novel cluster
  render_enrichment     — new approach/anti-pattern block(s) for an existing playbook

Both use a two-pass approach: draft → AEM-architect critic. The FORMAT.md
contract and two reference playbooks are injected into every system prompt
at runtime (read from handoff_dir) so the model always works from the
authoritative spec, not a cached copy.

Model-agnostic: uses complete_text / complete_json from llm/client.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cwv_playbook_miner.extraction.enrich_extract import EnrichmentEvidence
from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.extraction.semantic_cluster import NovelCluster
from cwv_playbook_miner.llm.client import complete_text

# ---------------------------------------------------------------------------
# Prompt builders (read live from handoff_dir so they stay current)
# ---------------------------------------------------------------------------

_STYLE_REFS = ("bundling.md", "lcp-image.md")   # good representatives of the format


def _load_format_spec(handoff_dir: Path) -> str:
    path = handoff_dir / "_FORMAT.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "(FORMAT.md not found)"


def _load_style_refs(handoff_dir: Path) -> str:
    parts = []
    for name in _STYLE_REFS:
        p = handoff_dir / name
        if p.exists():
            parts.append(f"=== EXAMPLE: {name} ===\n{p.read_text(encoding='utf-8')}\n")
    return "\n".join(parts)


def _load_existing_playbook(handoff_dir: Path, playbook_id: str) -> str:
    path = handoff_dir / f"{playbook_id}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _pr_evidence_block(prs: list[PRRecord], max_patch_chars: int = 5000) -> str:
    blocks = []
    for pr in prs:
        files = []
        for f in pr.changed_files[:6]:
            patch = (f.get("patch") or "")[:max_patch_chars // max(1, len(pr.changed_files[:6]))]
            if patch:
                files.append(f"File: {f.get('filename', '')}\n{patch}")
        blocks.append(
            f"Source PR: {pr.id}\n"
            f"Signal: {pr.signal_type}"
            + (f" | delta={pr.delta} ({pr.metric_key})" if pr.delta is not None else "")
            + f"\nTitle: {pr.title or '(unavailable)'}\n"
            + (f"Human signal: {pr.human_signal_text[:400]}\n" if pr.human_signal_text else "")
            + (f"PR body: {(pr.pr_body_markdown or '')[:1200]}\n" if pr.pr_body_markdown else "")
            + ("Changed files:\n" + "\n---\n".join(files) if files else "")
        )
    return "\n\n" + "=" * 60 + "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# New playbook (novel cluster)
# ---------------------------------------------------------------------------

_NEW_PLAYBOOK_DRAFT_SYSTEM = """\
You are an AEM web-performance architect authoring a new CWV playbook for the mystique code-fix agent.

## Contract (mandatory — every field and section)

{format_spec}

## Style reference (match this exactly)

{style_refs}

## Your task

Write a complete {{issue_type}}.md for the novel cluster described below.
- `applicable_flavors` must be a subset of [eds, cs, ams, headless] — exclude flavors where the fix does not apply
- `risk_tier`: low (safe auto-fix), medium (needs validation), high (recommendation-only)
- `required_validation`: snake_case IDs for pre-conditions the agent must check before emitting a diff
- `forbidden_techniques`: derive real Python `re` regex patterns from the anti-pattern code in the evidence PRs;
  write [] only if no clear bad-code pattern exists in the evidence
- Code examples MUST use AEM-native idioms:
    - EDS: block `decorate(block)` export, `import()` from block-relative paths, `IntersectionObserver`
    - CS/AMS: clientlib `.content.xml` with `categories`/`dependencies`, HTL `<sly data-sly-use>`, Sling models
    - Never use React, Next.js, Vue, Webpack config, or generic npm patterns as the primary example
- The Anti-patterns section must show a concrete bad code block (marked `<!-- Bad: ... -->` or `// Bad`) with
  `**Why this is bad:**` — one sentence, evidence-grounded
- Output ONLY the complete Markdown document starting with `---` (YAML front matter). No commentary before or after.
"""

_NEW_PLAYBOOK_CRITIC_SYSTEM = """\
You are a senior AEM architect doing a final quality review of a new CWV playbook.

Check and fix all of the following:
1. Front matter: `issue_type` matches filename, all required fields present, `applicable_flavors` correct
2. `forbidden_techniques` regex patterns are valid Python `re` syntax and not catastrophically backtracking
   (no `(a+)+` style nesting — use `\\s*` not `[\\s\\S]*` in repeated groups)
3. AEM code accuracy: EDS block code uses correct `export default function decorate(block)` signature;
   CS/AMS code uses `.content.xml` clientlib format, not package.json / webpack
4. `risk_tier` matches the fix complexity — auto-applying a clientlib split is medium, not low
5. All four required body sections present in order: What this addresses / When to apply / Recommended approaches / Anti-patterns
6. At least one concrete fenced code example marked Good in Recommended approaches
7. Anti-patterns section has a Bad example and **Why this is bad:** only when evidence supports it
8. No fabricated browser support percentages, no invented validation IDs, no AEM product names in issue_type

Rewrite any incorrect sections in place. Preserve everything that is already correct.
Output ONLY the complete revised Markdown document starting with `---`. No commentary.
"""


def render_new_playbook(
    cluster: NovelCluster,
    source_prs: list[PRRecord],
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 240,
) -> str:
    format_spec = _load_format_spec(handoff_dir)
    style_refs = _load_style_refs(handoff_dir)

    draft_system = _NEW_PLAYBOOK_DRAFT_SYSTEM.format(
        format_spec=format_spec,
        style_refs=style_refs,
    )

    approach_prs = [pr for pr in source_prs if pr.signal_type == "perf_improvement"]
    antipattern_prs = [pr for pr in source_prs if pr.signal_type in ("perf_decrease", "perf_flagged")]

    draft_user = f"""Novel cluster:
issue_type: {cluster.issue_type}
description: {cluster.description}
applicable_flavors: {cluster.applicable_flavors}
risk_tier: {cluster.risk_tier}
aem_rationale: {cluster.aem_rationale}
evidence: {cluster.positive_count} improvement PRs, {cluster.negative_count} regression PRs across {cluster.distinct_repo_count} repos
directional_consistency: {cluster.directional_consistency:.0%}

Representative technique summaries:
{chr(10).join(f"- {s}" for s in cluster.representative_summaries)}

Improvement evidence (Recommended approaches):
{_pr_evidence_block(approach_prs)}

Regression evidence (Anti-patterns):
{_pr_evidence_block(antipattern_prs) if antipattern_prs else "No regression evidence — use forbidden_techniques: []"}
"""

    draft = _extract_document(
        complete_text(draft_system, draft_user, backend=backend, model=model, timeout=timeout)
    )

    critic_user = f"""Evidence summary:
issue_type: {cluster.issue_type} | flavors: {cluster.applicable_flavors} | tier: {cluster.risk_tier}
{len(approach_prs)} improvement PRs, {len(antipattern_prs)} regression PRs

Draft to review and rewrite:
{draft}
"""
    final = _extract_document(
        complete_text(_NEW_PLAYBOOK_CRITIC_SYSTEM, critic_user, backend=backend, model=model, timeout=timeout)
    )
    return _reconcile_front_matter(final, cluster)


# ---------------------------------------------------------------------------
# Enrichment (add to existing playbook)
# ---------------------------------------------------------------------------

_ENRICH_DRAFT_SYSTEM = """\
You are an AEM web-performance architect adding new content to an existing CWV playbook.

## Existing playbook (do NOT rewrite — only extend)

{existing_playbook}

## Your task

Write ONLY the new content to add — one or both of:
  A. A new `### <Approach name>` subsection under `## Recommended approaches`
  B. A new `### <Anti-pattern name>` subsection under `## Anti-patterns`

Include A when the improvement evidence shows a technique not already covered.
Include B when the regression evidence shows a concrete bad-code pattern not already covered.

Rules (same as the format spec):
- Code examples use AEM-native idioms: EDS block decorate(), CS/AMS clientlib XML / HTL
- Anti-pattern subsection must include a fenced bad code block and `**Why this is bad:**`
- Approach subsection must include a fenced good code block
- No fabricated data; only what the evidence supports

Output ONLY the new Markdown block(s) — nothing else. No front matter, no full document rewrite.
"""

_ENRICH_CRITIC_SYSTEM = """\
You are an AEM architect reviewing new content proposed for an existing playbook.

Check:
1. Code accuracy for EDS/CS/AMS (correct signatures, no React/webpack patterns as primary examples)
2. Does not duplicate content already in the playbook (shown above the draft)
3. Anti-pattern has a concrete Bad example and **Why this is bad:**
4. Approach has a concrete Good example
5. Tone and heading style match the existing playbook

Output ONLY the corrected new content block(s). No commentary.
"""


def render_enrichment(
    evidence: EnrichmentEvidence,
    approach_prs: list[PRRecord],
    antipattern_prs: list[PRRecord],
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
) -> str:
    existing = _load_existing_playbook(handoff_dir, evidence.playbook_id)

    draft_system = _ENRICH_DRAFT_SYSTEM.format(existing_playbook=existing)

    draft_user = f"""Improvement evidence (new Recommended approaches):
{_pr_evidence_block(approach_prs) if approach_prs else "None"}

Regression evidence (new Anti-patterns):
{_pr_evidence_block(antipattern_prs) if antipattern_prs else "None"}

Technique summaries:
{chr(10).join(f"[improvement] {s}" for s in evidence.approach_summaries)}
{chr(10).join(f"[regression]  {s}" for s in evidence.antipattern_summaries)}
"""

    draft = complete_text(draft_system, draft_user, backend=backend, model=model, timeout=timeout).strip()

    critic_user = f"""Existing playbook (for duplicate-check):
{existing[:3000]}...

Proposed new content to review:
{draft}
"""
    return complete_text(_ENRICH_CRITIC_SYSTEM, critic_user, backend=backend, model=model, timeout=timeout).strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_document(text: str) -> str:
    """Pull the YAML-fronted markdown document out of any wrapper text."""
    fence = re.search(r"```(?:markdown)?\n(---[\s\S]+?)\n```", text)
    if fence:
        return fence.group(1).strip()
    idx = text.find("---")
    if idx != -1:
        return text[idx:].strip()
    return text.strip()


def _reconcile_front_matter(text: str, cluster: NovelCluster) -> str:
    """Ensure issue_type, applicable_flavors, and risk_tier in the front
    matter exactly match the cluster metadata (LLM sometimes drifts)."""
    try:
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not match:
            return text
        fm = yaml.safe_load(match.group(1)) or {}
        fm["issue_type"] = cluster.issue_type
        fm["applicable_flavors"] = cluster.applicable_flavors
        fm["risk_tier"] = cluster.risk_tier
        if "source_prs" not in fm:
            fm["source_prs"] = cluster.source_pr_ids[:20]
        fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
        return f"---\n{fm_yaml}\n---\n{match.group(2)}"
    except Exception:  # noqa: BLE001
        return text


def write_playbook(text: str, issue_type: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{issue_type}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_enrichment(text: str, playbook_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{playbook_id}.enrichment.md"
    path.write_text(text, encoding="utf-8")
    return path
