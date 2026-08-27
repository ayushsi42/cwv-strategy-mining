"""Stage 5b+6: generate AEM-format playbook files.

Two generation modes:
  render_new_playbook   — full {issue_type}.md for a novel, coherence-verified cluster
  render_enrichment     — new approach/anti-pattern block(s) for an existing playbook

Both use a three-pass approach: draft -> AEM-architect critic -> grounding
check. The FORMAT.md contract and two reference playbooks are injected into
every system prompt at runtime (read from handoff_dir) so the model always
works from the authoritative spec, not a cached copy. Evidence selection is
diversity-weighted (evidence_selection.py) so one repo's repeated pattern
can't dominate a technique's evidence on its own.

Model-agnostic: uses complete_text from llm/client.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.extraction.cluster import NovelCluster
from cwv_playbook_miner.extraction.enrich_extract import EnrichmentEvidence
from cwv_playbook_miner.extraction.evidence_selection import select_diverse
from cwv_playbook_miner.llm.client import complete_text

# ---------------------------------------------------------------------------
# Shared helpers (read live from handoff_dir so they stay current)
# ---------------------------------------------------------------------------

_STYLE_REFS = ("bundling.md", "lcp-image.md")   # good representatives of the format

MAX_APPROACH_PRS = 8
MAX_ANTIPATTERN_PRS = 6


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


def _extract_document(text: str) -> str:
    """Pull the YAML-fronted markdown document out of any wrapper text."""
    fence = re.search(r"```(?:markdown)?\n(---[\s\S]+?)\n```", text)
    if fence:
        return fence.group(1).strip()
    idx = text.find("---")
    if idx != -1:
        return text[idx:].strip()
    return text.strip()


def write_playbook(text: str, issue_type: str, output_dir: Path) -> Path:
    subdir = output_dir / "new_playbooks"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{issue_type}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_enrichment(text: str, playbook_id: str, output_dir: Path) -> Path:
    subdir = output_dir / "enriched"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{playbook_id}.enrichment.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Grounding check (stage 6) -- runs after draft+critic, before the document
# is considered final. Checks every concrete claim, especially anti-pattern
# "why this is bad" reasoning, actually traces to the cited evidence rather
# than being invented-but-plausible justification.
# ---------------------------------------------------------------------------

_GROUNDING_SYSTEM = """You are fact-checking a generated CWV playbook against its actual source evidence.
For every concrete claim -- especially any "Why this is bad" reasoning in the Anti-patterns section, any
specific number, and any claim about what a technique does -- verify it is actually supported by the
evidence PRs shown below. If a claim isn't supported, either remove it or soften it to what the evidence
actually shows (e.g. "can increase X" instead of a fabricated specific percentage).

Do not invent support for a claim that has none -- rewrite or cut it instead.
Output ONLY the complete, corrected Markdown document, unchanged from the input except where a claim
needed fixing. No commentary."""


def _grounding_check(text: str, evidence_block: str, backend: str, model: str | None, timeout: int) -> str:
    user = f"Evidence PRs:\n{evidence_block}\n\nGenerated document:\n{text}"
    checked = complete_text(_GROUNDING_SYSTEM, user, backend=backend, model=model, timeout=timeout)
    return _extract_document(checked) if "---" in checked[:50] else checked.strip()


# ---------------------------------------------------------------------------
# AEM-fidelity check -- a dedicated pass, not a critic sub-bullet. The
# critic's AEM check is narrow (EDS decorate() signature, CS/AMS clientlib-
# not-webpack) and doesn't catch a bare React/JSX example that has neither
# webpack nor package.json in sight -- confirmed live: the source evidence
# for several clusters was itself React code (e.g. row virtualization mined
# from a React app), and the draft model sometimes carried the source
# framework over almost verbatim instead of translating the technique into
# AEM-native terms. Runs last, after grounding, so it's the final gate on
# what actually ships.
# ---------------------------------------------------------------------------

_AEM_FIDELITY_SYSTEM = """You are an AEM platform engineer checking whether every code example in a CWV
playbook is genuinely implementable on the platform(s) its front matter's applicable_flavors claims --
eds, cs, ams, headless.

For each flavor listed, code examples in the MAIN body (## Recommended approaches / ## Anti-patterns --
not inside a ## Flavor-specific notes subsection) must use that flavor's real idioms:
- eds: block `decorate(block)` export, `import()` from block-relative paths, vanilla JS/CSS/HTML -- no
  build step, no npm package imports
- cs / ams: HTL (`<sly data-sly-...>`), Sling Models (Java), or clientlib `.content.xml` + vanilla JS/CSS
  loaded via categories/dependencies -- never React/Vue/JSX, never a bare npm package import as the
  primary mechanism
- headless: a JS framework (React, etc.) is legitimate ONLY when applicable_flavors is headless-only, or
  when that code lives inside a `### Headless` flavor-specific subsection -- never as the universal main-
  body example when eds/cs/ams are also claimed to apply

A code example FAILS when it uses React/Vue/Next.js/JSX/a bare npm package import as the primary "Good"
or "Bad" example for a flavor that isn't headless-only, when EDS code doesn't use decorate(block), or
when CS/AMS code uses package.json/webpack instead of clientlib format. This applies equally to "Bad"
examples in Anti-patterns -- an anti-pattern's code must still be code that would actually appear in the
claimed flavor's codebase, not a generic React mistake. A `.tsx`/`.jsx` fenced code block, or any use of
`useState`/`useEffect`/`useSelector`/`useMemo`/`React.`/`import ... from 'react'`/`from 'react-redux'`,
is a React idiom and fails for every non-headless-only flavor, full stop -- it is never "close enough" or
"illustrative pseudocode."

Before writing your output, go through the document top to bottom and individually check EVERY fenced
code block under `## Recommended approaches` and `## Anti-patterns` (both "Good" and "Bad" examples) --
do not stop after finding and fixing the first violation, and do not skip a block because it looks
framework-agnostic at a glance; check its actual contents and fenced language tag. A block inside
`## Flavor-specific notes` / `### Headless` is exempt; every other block under those two headings is not.

For each failure, REWRITE only that code example into a real, idiomatic equivalent for the claimed
flavor(s) -- keep the same underlying technique and behavior, translate the implementation. Do not
remove a flavor from applicable_flavors to dodge the check; translate the code to actually support it.
If every example already checks out, make no changes.

Output ONLY the complete, corrected Markdown document, identical to the input except where a code
example needed AEM-native translation. No commentary."""


def _aem_fidelity_check(text: str, backend: str, model: str | None, timeout: int, flavors_note: str = "") -> str:
    """flavors_note is only needed for enrichment blocks, which have no
    front matter of their own to read applicable_flavors from -- new
    playbooks carry that in the document text itself."""
    user = f"{flavors_note}\n\n{text}" if flavors_note else text
    checked = complete_text(_AEM_FIDELITY_SYSTEM, user, backend=backend, model=model, timeout=timeout)
    return _extract_document(checked) if "---" in checked[:50] else checked.strip()


# ---------------------------------------------------------------------------
# New playbook (novel, coherence-verified cluster)
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


def _split_front_matter(text: str) -> tuple[dict, str]:
    """Tolerant front-matter split -- the LLM has been observed to (a) omit
    the closing `---` fence entirely, and (b) write YAML-invalid escaping
    inside a forbidden_techniques regex (e.g. `[\\'"]` in a double-quoted
    scalar). Either one used to make the old regex-based parse silently
    fail and fall through a bare `except: return text`, which meant
    `source_prs` -- and every other programmatically-set field -- never
    actually landed in ANY of a real 9-playbook batch. Never silently give
    up here: worst case, return an empty dict and the whole body as text,
    and let the caller rebuild a correct front matter block from scratch."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    close_idx = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close_idx is None:
        # No closing fence -- guess the body starts at the first H1/H2 heading.
        close_idx = next((i for i in range(1, len(lines)) if lines[i].startswith("#")), len(lines))
        fm_text = "\n".join(lines[1:close_idx])
        body = "\n".join(lines[close_idx:])
    else:
        fm_text = "\n".join(lines[1:close_idx])
        body = "\n".join(lines[close_idx + 1:])

    try:
        fm = yaml.safe_load(fm_text)
        fm = fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        fm = {}
    return fm, body.lstrip("\n")


def _normalize_forbidden_techniques(raw) -> list[dict]:
    """The spec requires {pattern, reason} dicts; the LLM sometimes writes
    bare regex strings instead. Normalize rather than drop, and validate
    each pattern actually compiles as Python re (the spec's own contract)
    -- an invalid one gets dropped rather than shipped broken."""
    out = []
    for item in raw or []:
        if isinstance(item, dict) and item.get("pattern"):
            pattern, reason = item["pattern"], item.get("reason", "")
        elif isinstance(item, str) and item:
            pattern, reason = item, "Matches a known anti-pattern from the source evidence."
        else:
            continue
        try:
            re.compile(pattern)
        except re.error:
            continue
        out.append({"pattern": pattern, "reason": reason})
    return out


def _fix_when_to_apply_heading(body: str) -> str:
    return re.sub(
        r"^## When to apply\s*$", "## When to apply / when to skip", body,
        count=1, flags=re.MULTILINE,
    )


def _reconcile_front_matter(text: str, cluster: NovelCluster) -> str:
    """Guarantees issue_type/applicable_flavors/risk_tier/source_prs/
    forbidden_techniques are correct and present, regardless of how the
    LLM formatted (or malformed) its own front matter -- these are exactly
    the fields the checklist and the loader depend on, so this never
    falls back to "leave it as the model wrote it"."""
    fm, body = _split_front_matter(text)
    fm["issue_type"] = cluster.issue_type
    fm["applicable_flavors"] = cluster.applicable_flavors
    fm["risk_tier"] = cluster.risk_tier
    fm["forbidden_techniques"] = _normalize_forbidden_techniques(fm.get("forbidden_techniques"))
    fm.setdefault("required_validation", [])
    fm["source_prs"] = cluster.source_pr_ids[:20]

    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    body = _fix_when_to_apply_heading(body)
    return f"---\n{fm_yaml}\n---\n{body}"


def render_new_playbook(
    cluster: NovelCluster,
    pr_by_id: dict[str, PRRecord],
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 240,
) -> str:
    format_spec = _load_format_spec(handoff_dir)
    style_refs = _load_style_refs(handoff_dir)
    draft_system = _NEW_PLAYBOOK_DRAFT_SYSTEM.format(format_spec=format_spec, style_refs=style_refs)

    # cluster.pr_directions resolves perf_improvement/perf_decrease directly and
    # perf_flagged via the relevance-judged inferred direction (never guessed --
    # "unclear"/unclassified perf_flagged PRs are absent from the dict, so they
    # still ride along in cluster.source_pr_ids but aren't used as evidence here).
    approach_prs = select_diverse(
        [pr_by_id[pid] for pid in cluster.source_pr_ids if cluster.pr_directions.get(pid) == "positive" and pid in pr_by_id],
        MAX_APPROACH_PRS,
    )
    antipattern_prs = select_diverse(
        [pr_by_id[pid] for pid in cluster.source_pr_ids if cluster.pr_directions.get(pid) == "negative" and pid in pr_by_id],
        MAX_ANTIPATTERN_PRS,
    )

    approach_block = _pr_evidence_block(approach_prs)
    antipattern_block = _pr_evidence_block(antipattern_prs) if antipattern_prs else "No regression evidence — use forbidden_techniques: []"

    draft_user = f"""Novel cluster:
issue_type: {cluster.issue_type}
description: {cluster.description}
applicable_flavors: {cluster.applicable_flavors}
risk_tier: {cluster.risk_tier}
aem_rationale: {cluster.aem_rationale}
evidence: {cluster.positive_count} improvement PRs, {cluster.negative_count} regression PRs across {cluster.distinct_repo_count} repos
directional_consistency: {cluster.directional_consistency:.0%}

Improvement evidence (Recommended approaches):
{approach_block}

Regression evidence (Anti-patterns):
{antipattern_block}
"""
    draft = _extract_document(complete_text(draft_system, draft_user, backend=backend, model=model, timeout=timeout))

    critic_user = f"""Evidence summary:
issue_type: {cluster.issue_type} | flavors: {cluster.applicable_flavors} | tier: {cluster.risk_tier}
{len(approach_prs)} improvement PRs, {len(antipattern_prs)} regression PRs

Draft to review and rewrite:
{draft}
"""
    critiqued = _extract_document(complete_text(_NEW_PLAYBOOK_CRITIC_SYSTEM, critic_user, backend=backend, model=model, timeout=timeout))

    full_evidence = approach_block + "\n\n" + antipattern_block
    grounded = _grounding_check(critiqued, full_evidence, backend, model, timeout)
    aem_checked = _aem_fidelity_check(grounded, backend, model, timeout)

    return _reconcile_front_matter(aem_checked, cluster)


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
    pr_by_id: dict[str, PRRecord],
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
) -> str:
    approach_prs = [pr_by_id[pid] for pid in evidence.approach_pr_ids if pid in pr_by_id]
    antipattern_prs = [pr_by_id[pid] for pid in evidence.antipattern_pr_ids if pid in pr_by_id]

    existing = _load_existing_playbook(handoff_dir, evidence.playbook_id)
    draft_system = _ENRICH_DRAFT_SYSTEM.format(existing_playbook=existing)

    approach_block = _pr_evidence_block(approach_prs) if approach_prs else "None"
    antipattern_block = _pr_evidence_block(antipattern_prs) if antipattern_prs else "None"

    draft_user = f"""Improvement evidence (new Recommended approaches):
{approach_block}

Regression evidence (new Anti-patterns):
{antipattern_block}
"""
    draft = complete_text(draft_system, draft_user, backend=backend, model=model, timeout=timeout).strip()

    critic_user = f"""Existing playbook (for duplicate-check):
{existing[:3000]}...

Proposed new content to review:
{draft}
"""
    critiqued = complete_text(_ENRICH_CRITIC_SYSTEM, critic_user, backend=backend, model=model, timeout=timeout).strip()

    full_evidence = approach_block + "\n\n" + antipattern_block
    grounded = _grounding_check(critiqued, full_evidence, backend, model, timeout).strip()

    existing_fm, _ = _split_front_matter(existing)
    flavors = existing_fm.get("applicable_flavors") or []
    flavors_note = (
        f"applicable_flavors for the playbook this content is being added to: {flavors}"
        if flavors else ""
    )
    aem_checked = _aem_fidelity_check(grounded, backend, model, timeout, flavors_note=flavors_note)

    return aem_checked + "\n\n" + _source_pr_note(evidence.approach_pr_ids, evidence.antipattern_pr_ids)


def _source_pr_note(approach_pr_ids: list[str], antipattern_pr_ids: list[str]) -> str:
    """Enrichment blocks are spliced into an existing playbook's body, not a
    standalone document, so they never get their own YAML front matter --
    but the checklist requires grounding by source PR regardless. A small
    marked note (not a fabricated field the loader might try to parse)
    keeps that traceable in the file itself, not only in enrichments.jsonl."""
    parts = []
    if approach_pr_ids:
        parts.append(f"**approach:** {', '.join(approach_pr_ids)}")
    if antipattern_pr_ids:
        parts.append(f"**anti-pattern:** {', '.join(antipattern_pr_ids)}")
    return f"> **Source PRs** — {' · '.join(parts)}" if parts else ""
