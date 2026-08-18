"""Stage 2: one LLM call per PRRecord, extracting a generalizable technique.
Shaped the same way as smol-planner's cwv_pattern_mining.py's extract stage
(same schema: technique/problem_symptom/code_pattern/why_it_works/
applicable_signal/framework_hint) since it solves the same sub-problem --
"turn one real diff + real delta into one reusable, human-readable pattern"
-- rebuilt fresh here against this pipeline's own PRRecord shape.

Runs against both perf_improvement records (recommended-approach grounding)
and perf_decrease records (anti-pattern grounding, stage 5) -- same
extraction schema either way, direction is carried by PRRecord.signal_type.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import LLMError, complete_json

SYSTEM_PROMPT = """You are a web performance engineer studying a real, merged GitHub \
pull request with a measured Core Web Vitals / Lighthouse-style performance change. \
You are given the real diff and the real before/after metric. Extract ONE generalizable \
optimization (or regression, if the PR made things worse) pattern from this PR -- \
something a future engineer could recognize and reapply/avoid on a different repo, not a \
description specific to this one PR.

Return STRICT JSON only, matching this schema exactly:
{
  "technique": "<short, reusable name, e.g. 'lazy-load below-the-fold images', 'defer non-critical third-party scripts'>",
  "problem_symptom": "<what a Lighthouse audit or slow-loading page looks like when this problem is present, in general terms>",
  "code_pattern": "<the generalized code change, described or as a short illustrative snippet -- not the literal diff, the reusable pattern behind it>",
  "why_it_works": "<one sentence, the mechanism by which this improves (or, for a regression, worsens) the measured metric>",
  "framework_hint": "<framework/stack this applies to, or 'any' if framework-agnostic>",
  "applicable_signal": "<what a real Lighthouse/CWV audit finding would look like to trigger recommending this pattern, e.g. 'render-blocking resources', 'large LCP image', 'unused CSS'>",
  "mechanism": "<short normalized action, e.g. defer, preload, resize, remove-work, cache>",
  "affected_resource": "<short normalized target, e.g. offscreen-images, web-fonts, main-thread-js, html>",
  "render_phase": "<initial-load | interaction | server-response | background>"
}

Return {"technique": null} and nothing else if the diff is NOT a real, reusable, PAGE-FACING \
Core Web Vitals technique. Confirmed live that this distinction gets missed without being \
spelled out explicitly, so apply it strictly -- null out anything that is:
- CI/build pipeline speed or reliability (test caching, parallelizing CI jobs, stabilizing \
  flaky measurements by averaging runs) -- this changes how fast/reliably you MEASURE the \
  site, not the site a real visitor experiences. "Use the median of N Lighthouse runs" is \
  NOT a technique, even though it appeared in a PR with a real score delta.
- Test infrastructure (fixtures, mocks, test bundle isolation) -- affects test suite speed, \
  not the shipped page.
- A generic dependency/toolchain version bump with no described mechanism for HOW it \
  improves the page (e.g. "upgrade bundler CSS deps") -- if you can't name what the diff \
  actually changed about the page's loading/rendering/scripting behavior, it's not a technique.
- A pure UI/UX redesign with no performance mechanism (e.g. swapping to a different UI \
  library's component, or making images visually larger for a nicer layout) -- unless the \
  diff itself explains a real loading/rendering mechanism, a redesign is not a technique.
- A correctness/security bug fix whose primary purpose is fixing wrong behavior (e.g. \
  stale cached data leaking between users), even if it incidentally touches caching code.
Only return a technique when the diff clearly changes what the BROWSER downloads, parses, \
renders, or executes for a real page visit."""


def build_prompt(record: PRRecord) -> str:
    diff_parts = []
    for cf in record.changed_files[:6]:
        patch = (cf.get("patch") or "")[:1500]
        diff_parts.append(f"--- {cf['filename']} ---\n{patch}")
    diff_text = "\n\n".join(diff_parts)
    direction = "improved" if record.signal_type == "perf_improvement" else "regressed"
    return f"""Repo: {record.repo}
PR title: {record.title or '(no title)'}
Signal: {record.signal_type} ({direction} {record.metric_key} from {record.before} to {record.after}, delta {record.delta})

PR description:
{(record.pr_body_markdown or '(empty)')[:2000]}

Diff:
{diff_text}

Return the JSON now."""


@dataclass
class ExtractedPattern:
    source_id: str
    source_repo: str
    signal_type: str
    technique: str
    problem_symptom: str
    code_pattern: str
    why_it_works: str
    framework_hint: str
    applicable_signal: str
    measured_delta: dict = field(default_factory=dict)
    mechanism: str = ""
    affected_resource: str = ""
    render_phase: str = ""


def extract_pattern(record: PRRecord, backend: str, model: str | None, timeout: int) -> ExtractedPattern | None:
    try:
        extracted = complete_json(SYSTEM_PROMPT, build_prompt(record), backend=backend, model=model, timeout=timeout)
    except LLMError as exc:
        # Previously swallowed silently -- indistinguishable from a genuine
        # "technique: null" judgment in the CLI's "skipped" output. Surface
        # it: confirmed live this backend (claude-cli, no temperature
        # control via `-p`) is non-deterministic enough that a real call
        # sometimes fails formatting/parsing where an identical retry
        # succeeds -- worth knowing which happened, not guessing.
        print(f"    LLM call failed for {record.id}: {exc}")
        return None
    technique = extracted.get("technique") if extracted else None
    if (
        not isinstance(technique, str)
        or not technique.strip()
        or technique.strip().lower() in {"null", "none", "n/a"}
    ):
        return None
    return ExtractedPattern(
        source_id=record.id, source_repo=record.repo, signal_type=record.signal_type,
        technique=technique, problem_symptom=extracted.get("problem_symptom", ""),
        code_pattern=extracted.get("code_pattern", ""), why_it_works=extracted.get("why_it_works", ""),
        framework_hint=extracted.get("framework_hint", "any"), applicable_signal=extracted.get("applicable_signal", ""),
        measured_delta={"metric_key": record.metric_key, "before": record.before,
                         "after": record.after, "delta": record.delta},
        mechanism=extracted.get("mechanism", ""),
        affected_resource=extracted.get("affected_resource", ""),
        render_phase=extracted.get("render_phase", ""),
    )


def extract_patterns(
    records: list[PRRecord], backend: str, model: str | None, timeout: int, concurrency: int = 8,
) -> list[ExtractedPattern]:
    """Concurrent (mirrors smol-planner's cwv_pattern_mining.py's own
    ThreadPoolExecutor-based extract stage) -- each record is an independent
    LLM call (subprocess for claude-cli, HTTP request for openai), so this
    is a real, needed speedup once record volume is more than a handful:
    sequential extraction over the external corpus's ~80 delta>=15 records
    would take on the order of 20+ minutes one-at-a-time."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    patterns: list[ExtractedPattern] = []
    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(extract_pattern, r, backend, model, timeout): r for r in records}
        for future in as_completed(futures):
            record = futures[future]
            pattern = future.result()
            done += 1
            if pattern:
                patterns.append(pattern)
            print(f"  [{done}/{len(records)}] {record.id}: {'ok -> ' + pattern.technique if pattern else 'skipped'}")
    return patterns


def write_jsonl(patterns: list[ExtractedPattern], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(asdict(p)) + "\n")


def read_jsonl(path: Path) -> list[ExtractedPattern]:
    patterns = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            patterns.append(ExtractedPattern(**json.loads(line)))
    return patterns
