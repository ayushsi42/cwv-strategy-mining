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


PROMPT_VERSION = "fused-extraction-v2"
BROAD_TECHNIQUE_FAMILIES = {
    "reduce-shipped-javascript": "Reduce shipped JavaScript",
    "defer-non-critical-work": "Defer non-critical work",
    "optimize-critical-images": "Optimize critical images",
    "eliminate-redundant-computation": "Eliminate redundant computation",
    "reuse-cache-and-data": "Reuse cached data and requests",
    "stabilize-layout": "Stabilize layout",
    "optimize-css-delivery": "Optimize CSS delivery",
    "optimize-font-delivery": "Optimize font delivery",
    "reduce-network-payload": "Reduce network payload",
    "reduce-server-response-time": "Reduce server response time",
    "reduce-third-party-cost": "Reduce third-party cost",
    "optimize-interaction-work": "Optimize interaction work",
}

FAMILY_REQUIRED_TERMS = {
    "reduce-shipped-javascript": ("javascript", "bundle", "chunk", "code split", "lazy route", "unused js"),
    "defer-non-critical-work": ("defer", "lazy", "delay", "postpone", "on demand", "below fold"),
    "optimize-critical-images": ("image", "hero", "lcp"),
    "eliminate-redundant-computation": ("duplicate", "redundant", "compute", "parse", "regex", "loop", "memo"),
    "reuse-cache-and-data": ("cache", "persisted", "reuse", "already", "duplicate roundtrip", "skip an extra"),
    "stabilize-layout": ("layout", "cls", "shift", "skeleton", "reserve", "fouc", "theme flash"),
    "optimize-css-delivery": ("css", "stylesheet", "style"),
    "optimize-font-delivery": ("font", "woff", "typeface"),
    "reduce-network-payload": ("payload", "transfer", "bytes", "response size", "download"),
    "reduce-server-response-time": ("ttfb", "server response", "origin latency", "backend latency"),
    "reduce-third-party-cost": ("third party", "third-party", "vendor script", "tracking script"),
    "optimize-interaction-work": ("interaction", "inp", "event handler", "input delay", "main thread"),
}

_FAMILY_LINES = "\n".join(
    f'- "{key}": {label}' for key, label in BROAD_TECHNIQUE_FAMILIES.items()
)
SYSTEM_PROMPT = f"""You are a strict web-performance evidence extractor. Evaluate every supplied
GitHub PR independently. Return one result carrying the same source_id for every input.

A valid observation must directly change what a real visitor's browser downloads, parses,
renders or executes, or directly reduce origin response latency. Reject accessibility-only,
visual/UX, correctness, security, test, CI, build-speed, social-preview, metadata and generic
dependency-upgrade changes even when a coincident Lighthouse score changed.

For valid observations, select exactly one broad_family from this controlled taxonomy:
{_FAMILY_LINES}

The specific change must implement the named family mechanism, not merely accompany it.
For example: hiding columns is not reduced shipped JavaScript; metadata deduplication and
prop merging are not cache/request reuse; a visual image resize is not critical-image
optimization; onboarding hints are not deferred work; CSS variables are not network-payload
reduction; client-side execution is not third-party-cost reduction; build/postinstall work is
never font delivery. Reject a record when no family is a direct, defensible fit.

Return strict JSON:
{{"results": [{{
  "source_id": "exact input id",
  "is_page_performance": true,
  "rejection_reason": "empty when accepted; concise reason when rejected",
  "broad_family": "one taxonomy key or null",
  "technique": "short specific reusable variant or null",
  "problem_symptom": "audit/page symptom",
  "code_pattern": "generalized change",
  "why_it_works": "direct browser/server performance mechanism",
  "framework_hint": "framework or any",
  "applicable_signal": "CWV/Lighthouse trigger",
  "mechanism": "normalized action",
  "affected_resource": "normalized target",
  "render_phase": "initial-load | interaction | server-response | background"
}}]}}

Do not infer performance from score correlation alone. A rejected item must use false, null
broad_family, and null technique. Do not omit input records."""


def _compact_record(record: PRRecord) -> dict:
    files = []
    for changed_file in record.changed_files[:6]:
        files.append({
            "filename": changed_file.get("filename", ""),
            "patch": (changed_file.get("patch") or "")[:1500],
        })
    return {
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
    broad_family: str = ""


def _to_pattern(record: PRRecord, extracted: dict) -> ExtractedPattern | None:
    technique = extracted.get("technique")
    family = extracted.get("broad_family")
    evidence_text = " ".join(str(extracted.get(key, "") or "") for key in (
        "technique", "problem_symptom", "code_pattern", "why_it_works", "mechanism",
        "affected_resource", "applicable_signal",
    )).lower().replace("-", " ")
    coherent_family = family in FAMILY_REQUIRED_TERMS and any(
        term in evidence_text for term in FAMILY_REQUIRED_TERMS.get(family, ())
    )
    if family == "reuse-cache-and-data" and (
        "fallback request" in evidence_text or "second request" in evidence_text
    ):
        coherent_family = False
    if (
        extracted.get("is_page_performance") is not True
        or not isinstance(technique, str)
        or not technique.strip()
        or technique.strip().lower() in {"null", "none", "n/a"}
        or family not in BROAD_TECHNIQUE_FAMILIES
        or not coherent_family
    ):
        return None
    return ExtractedPattern(
        source_id=record.id,
        source_repo=record.repo,
        signal_type=record.signal_type,
        technique=technique.strip(),
        broad_family=family,
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
    record_by_id = {record.id: record for record in records}

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
        print(f"  {record.id}: {'ok -> ' + pattern.broad_family + ' / ' + pattern.technique if pattern else 'rejected'}")
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
            patterns.append(ExtractedPattern(**payload))
    return patterns
