"""Fused, batched extraction of reusable page-performance observations.

One completion evaluates several compact PR records and returns both the
performance-validity decision and normalized technique fields. Results are
cached per record/content/prompt version, so unchanged PRs are never sent to
the model twice even when batch boundaries or concurrency change.
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import complete_json
from cwv_playbook_miner.taxonomy import PARENT_STRATEGIES, parent_taxonomy_prompt


PROMPT_VERSION = "hierarchical-extraction-v2"

SYSTEM_PROMPT = f"""You are a strict web-performance evidence extractor. Evaluate every supplied
GitHub PR independently. Return one result carrying the same source_id for every input.

A valid observation must directly change what a real visitor's browser downloads, parses,
renders or executes, or directly reduce origin response latency. Reject accessibility-only,
visual/UX, correctness, security, test, CI, build-speed, social-preview, metadata and generic
dependency-upgrade changes even when a coincident Lighthouse score changed.

For valid observations, select exactly one parent_strategy from this stable taxonomy:
{parent_taxonomy_prompt()}

Also propose a reusable sub_strategy. It must describe the concrete mechanism at a level
that can recur across repositories: for example "route-level code splitting", "reserve
space for async content", or "reuse request-scoped authenticated user data". It must not
contain a repository, product, component, route, or framework-specific name.

The specific change must implement the named family mechanism, not merely accompany it.
For example: hiding columns is not reduced shipped JavaScript; metadata deduplication and
prop merging are not cache/request reuse; a visual image resize is not critical-image
optimization; onboarding hints are not deferred work; CSS variables are not network-payload
reduction; client-side execution is not third-party-cost reduction; build/postinstall work is
never font delivery. Reject a record when no family is a direct, defensible fit.

Some inputs have signal_type "perf_flagged": a human reviewer wrote something performance-related
about this merged PR (given as "human_signal"), but no bot posted a parseable before/after number,
so metric.key/before/after/delta are all null. For these, judge relevance from the diff and the
human_signal text exactly as you would any other input, and also set inferred_signal_type to
"perf_improvement" or "perf_decrease" -- your best-judgment direction of the change -- only when the
diff and human_signal make it reasonably clear; otherwise null. Leave inferred_signal_type null for
every other input (its own signal_type is already known).

Return strict JSON:
{{"results": [{{
  "source_id": "exact input id",
  "is_page_performance": true,
  "rejection_reason": "empty when accepted; concise reason when rejected",
  "parent_strategy": "one stable taxonomy key or null",
  "sub_strategy": "short reusable mechanism or null",
  "proposed_parent_strategy": "short proposal only when none of the 15 parents fits; otherwise null",
  "technique": "short specific reusable variant or null",
  "problem_symptom": "audit/page symptom",
  "code_pattern": "generalized change",
  "why_it_works": "direct browser/server performance mechanism",
  "framework_hint": "framework or any",
  "applicable_signal": "CWV/Lighthouse trigger",
  "mechanism": "normalized action",
  "affected_resource": "normalized target",
  "render_phase": "initial-load | interaction | server-response | background",
  "inferred_signal_type": "perf_improvement | perf_decrease | null -- only for perf_flagged inputs"
}}]}}

Do not infer performance from score correlation alone. A rejected item must use false and
null parent_strategy, sub_strategy, and technique. If a valid technique genuinely fits none
of the 15 parents, set parent_strategy null and proposed_parent_strategy; it will enter a
provisional review pool rather than automatically expanding the taxonomy. Do not omit inputs."""


def _compact_record(record: PRRecord) -> dict:
    files = []
    for changed_file in record.changed_files[:6]:
        files.append({
            "filename": changed_file.get("filename", ""),
            "patch": (changed_file.get("patch") or "")[:1500],
        })
    compact = {
        "source_id": record.id,
        "repo": record.repo,
        "title": record.title or "",
        "signal_type": record.signal_type,
        "metric": {
            "key": record.metric_key,
            "before": record.before,
            "after": record.after,
            "delta": record.delta,
        },
        "description": (record.pr_body_markdown or "")[:2000],
        "changed_files": files,
    }
    if record.human_signal_text:
        compact["human_signal"] = record.human_signal_text[:500]
    return compact


def build_batch_prompt(records: list[PRRecord]) -> str:
    return "Evaluate these records:\n" + json.dumps(
        [_compact_record(record) for record in records], separators=(",", ":"), ensure_ascii=False,
    )


def _cache_key(record: PRRecord, backend: str, model: str | None) -> str:
    effective_model = model or (
        os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
        if backend == "openai" else os.environ.get("LLM_MODEL_NAME", "default")
    )
    payload = {
        "prompt_version": PROMPT_VERSION,
        "backend": backend,
        "model": effective_model,
        "record": _compact_record(record),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
    parent_strategy: str = ""
    sub_strategy: str = ""
    sub_strategy_aliases: list[str] = field(default_factory=list)
    proposed_parent_strategy: str = ""
    broad_family: str = ""  # legacy field; ignored by hierarchical aggregation


def _resolve_signal_type(record: PRRecord, extracted: dict) -> str | None:
    """perf_improvement/perf_decrease records already know their polarity
    (a structured bot template parsed it in stage 1). perf_flagged records
    never had one -- match_template's generic_fallback always returns None
    for prose, so there's no delta to trust -- polarity must come from the
    LLM's own judgment of the diff + human_signal_text instead. Returning
    None here (rather than guessing) drops the record before it ever
    reaches aggregation, which trusts pattern.signal_type verbatim for
    positive_count/negative_count."""
    if record.signal_type != "perf_flagged":
        return record.signal_type
    inferred = extracted.get("inferred_signal_type")
    return inferred if inferred in ("perf_improvement", "perf_decrease") else None


def _to_pattern(record: PRRecord, extracted: dict) -> ExtractedPattern | None:
    technique = extracted.get("technique")
    parent = extracted.get("parent_strategy")
    sub_strategy = extracted.get("sub_strategy")
    proposed_parent = extracted.get("proposed_parent_strategy") or ""
    valid_parent = parent in PARENT_STRATEGIES
    signal_type = _resolve_signal_type(record, extracted)
    if (
        signal_type is None
        or extracted.get("is_page_performance") is not True
        or not isinstance(technique, str)
        or not technique.strip()
        or technique.strip().lower() in {"null", "none", "n/a"}
        or (not valid_parent and not proposed_parent.strip())
        or not isinstance(sub_strategy, str)
        or not sub_strategy.strip()
    ):
        return None
    return ExtractedPattern(
        source_id=record.id,
        source_repo=record.repo,
        signal_type=signal_type,
        technique=technique.strip(),
        parent_strategy=parent if valid_parent else "unclassified",
        sub_strategy=sub_strategy.strip(),
        proposed_parent_strategy=proposed_parent,
        problem_symptom=extracted.get("problem_symptom", ""),
        code_pattern=extracted.get("code_pattern", ""),
        why_it_works=extracted.get("why_it_works", ""),
        framework_hint=extracted.get("framework_hint", "any"),
        applicable_signal=extracted.get("applicable_signal", ""),
        measured_delta={
            "metric_key": record.metric_key, "before": record.before,
            "after": record.after, "delta": record.delta,
        },
        mechanism=extracted.get("mechanism", ""),
        affected_resource=extracted.get("affected_resource", ""),
        render_phase=extracted.get("render_phase", ""),
    )


def _read_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True))


def _extract_batch(
    records: list[PRRecord], backend: str, model: str | None, timeout: int,
) -> dict[str, dict]:
    result = complete_json(
        SYSTEM_PROMPT, build_batch_prompt(records), backend=backend, model=model, timeout=timeout,
    )
    items = result.get("results", [])
    allowed_ids = {record.id for record in records}
    return {
        item["source_id"]: item for item in items
        if isinstance(item, dict) and item.get("source_id") in allowed_ids
    }


def extract_patterns(
    records: list[PRRecord], backend: str, model: str | None, timeout: int,
    concurrency: int = 4, batch_size: int = 8, cache_dir: Path | None = None,
) -> list[ExtractedPattern]:
    """Extract records in bounded batches, reusing per-record content cache."""
    cache_dir = cache_dir or Path("data/processed/llm_cache/extraction")
    extracted_by_id: dict[str, dict] = {}
    misses: list[PRRecord] = []
    for record in records:
        cached = _read_cache(cache_dir / f"{_cache_key(record, backend, model)}.json")
        if cached is None:
            misses.append(record)
        else:
            extracted_by_id[record.id] = cached

    batches = [misses[index:index + batch_size] for index in range(0, len(misses), batch_size)]
    print(f"  extraction cache: {len(records) - len(misses)} hit(s), {len(misses)} miss(es), {len(batches)} LLM batch(es)")
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(_extract_batch, batch, backend, model, timeout): batch for batch in batches
        }
        for future in as_completed(futures):
            batch = futures[future]
            try:
                results = future.result()
            except Exception as exc:  # batch failure is visible and remains uncached
                print(f"    LLM batch failed ({len(batch)} records): {exc}")
                continue
            for record in batch:
                item = results.get(record.id)
                if item is None:
                    print(f"    LLM omitted {record.id}; left uncached for retry")
                    continue
                extracted_by_id[record.id] = item
                _write_cache(cache_dir / f"{_cache_key(record, backend, model)}.json", item)

    patterns = []
    for record in records:
        item = extracted_by_id.get(record.id)
        pattern = _to_pattern(record, item) if item else None
        if pattern:
            patterns.append(pattern)
        print(f"  {record.id}: {'ok -> ' + pattern.parent_strategy + ' / ' + pattern.sub_strategy if pattern else 'rejected'}")
    return patterns


def write_jsonl(patterns: list[ExtractedPattern], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for pattern in patterns:
            handle.write(json.dumps(asdict(pattern)) + "\n")


def read_jsonl(path: Path) -> list[ExtractedPattern]:
    patterns = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            payload.setdefault("broad_family", "")
            payload.setdefault("parent_strategy", "")
            payload.setdefault("sub_strategy", payload.get("technique", ""))
            payload.setdefault("sub_strategy_aliases", [])
            payload.setdefault("proposed_parent_strategy", "")
            patterns.append(ExtractedPattern(**payload))
    return patterns
