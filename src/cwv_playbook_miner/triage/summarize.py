"""Stage 1a: compact one-phrase technique summaries for each PR record.

Batches 50 records per LLM call — cheap on any small model (Haiku, Mistral-7B,
Llama-3-8B). The summary is the sole input to the embedding step: a tight,
specific phrase yields better cosine geometry than passing raw diff text.

Cache is keyed on record id + content hash + prompt version, so re-runs never
re-call the model for unchanged records.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import LLMError, complete_json

PROMPT_VERSION = "triage-summary-v1"
BATCH_SIZE = 50

SYSTEM_PROMPT = """You are a web-performance analyst. For each PR record below, write a one-phrase
technique summary (3–8 words) describing the specific frontend performance mechanism the PR implements.

Rules:
- Be concrete and mechanism-specific: "lazy-load block assets with IntersectionObserver" not "improve performance"
- Draw from the diff content, not just the PR title
- Write exactly the word DROP (nothing else) when the PR has no frontend rendering/delivery relevance:
    backend-only, CI/test/docs/security, dependency bumps with no behavior change,
    accessibility or visual changes not affecting load metrics, build-tooling only

Return strict JSON — one entry per input, same order:
{"summaries": [{"id": "<source_id>", "summary": "<phrase or DROP>"}]}
Do not omit any input record."""


@dataclass
class TriageSummary:
    record_id: str
    summary: str        # technique phrase, or "DROP"
    is_drop: bool


def _compact(record: PRRecord) -> dict:
    files = [
        {"filename": f.get("filename", ""), "patch": (f.get("patch") or "")[:800]}
        for f in record.changed_files[:5]
    ]
    return {
        "id": record.id,
        "title": record.title or "",
        "signal_type": record.signal_type,
        "human_signal": (record.human_signal_text or "")[:300],
        "description": (record.pr_body_markdown or "")[:800],
        "files": files,
    }


def _cache_key(record: PRRecord) -> str:
    payload = json.dumps(_compact(record), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{PROMPT_VERSION}:{record.id}:{digest}"


def _load_cache(cache_dir: Path) -> dict[str, TriageSummary]:
    path = cache_dir / "triage_summaries.jsonl"
    if not path.exists():
        return {}
    out: dict[str, TriageSummary] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["cache_key"]] = TriageSummary(
                record_id=d["record_id"],
                summary=d["summary"],
                is_drop=d["is_drop"],
            )
    return out


def _save_cache(entries: list[tuple[str, TriageSummary]], cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "triage_summaries.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for key, s in entries:
            f.write(json.dumps({"cache_key": key, **asdict(s)}) + "\n")


def _call_batch(
    batch: list[PRRecord],
    backend: str,
    model: str | None,
    timeout: int,
) -> list[TriageSummary]:
    user = "Records:\n" + json.dumps(
        [_compact(r) for r in batch], separators=(",", ":"), ensure_ascii=False
    )
    result = complete_json(SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
    by_id = {item["id"]: item["summary"] for item in result.get("summaries", [])}
    summaries = []
    for record in batch:
        summary = by_id.get(record.id, "DROP")
        summaries.append(TriageSummary(
            record_id=record.id,
            summary=summary,
            is_drop=(summary.strip().upper() == "DROP"),
        ))
    return summaries


def summarize_records(
    records: list[PRRecord],
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 120,
    workers: int = 8,
    cache_dir: Path | None = None,
) -> list[TriageSummary]:
    """Produce one TriageSummary per record. Uses cache to avoid re-calling the
    model for unchanged records across runs."""
    cache: dict[str, TriageSummary] = {}
    if cache_dir:
        cache = _load_cache(cache_dir)

    pending: list[tuple[int, PRRecord, str]] = []  # (original_index, record, cache_key)
    results: list[TriageSummary | None] = [None] * len(records)

    for i, record in enumerate(records):
        key = _cache_key(record)
        if key in cache:
            results[i] = cache[key]
        else:
            pending.append((i, record, key))

    print(f"  triage-summarize: {len(records)} records, "
          f"{len(results) - len(pending)} cached, {len(pending)} to call")

    if not pending:
        return [r for r in results if r is not None]

    # Batch into groups of BATCH_SIZE
    batches: list[list[tuple[int, PRRecord, str]]] = []
    for start in range(0, len(pending), BATCH_SIZE):
        batches.append(pending[start:start + BATCH_SIZE])

    new_cache_entries: list[tuple[str, TriageSummary]] = []
    completed = 0

    def _process_batch(batch_items: list[tuple[int, PRRecord, str]]) -> list[tuple[int, TriageSummary, str]]:
        batch_records = [item[1] for item in batch_items]
        try:
            summaries = _call_batch(batch_records, backend, model, timeout)
        except LLMError as exc:
            print(f"    batch LLM error: {exc} — marking as DROP")
            summaries = [
                TriageSummary(record_id=r.id, summary="DROP", is_drop=True)
                for r in batch_records
            ]
        return [(batch_items[j][0], summaries[j], batch_items[j][2]) for j in range(len(batch_items))]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process_batch, batch): batch for batch in batches}
        for future in as_completed(futures):
            for idx, summary, cache_key in future.result():
                results[idx] = summary
                new_cache_entries.append((cache_key, summary))
            completed += len(futures[future])
            print(f"    summarized {completed}/{len(pending)} pending records")

    if cache_dir and new_cache_entries:
        _save_cache(new_cache_entries, cache_dir)

    return [r for r in results if r is not None]
