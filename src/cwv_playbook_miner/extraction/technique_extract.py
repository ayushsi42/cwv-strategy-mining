"""Stage 1: rich per-PR technique extraction.

Extracts objective, checkable facts from the PR's full context (title,
body, diff, comments/reviews -- all real, via enrichment/pr_text.py). The
point: a fixed, LLM-invented taxonomy bucket can't guarantee "same
technique -> same category" because nothing ever validated the bucket
boundaries. Concrete, verifiable facts (what mechanism, on what resource,
at what render phase) can be checked against the actual diff -- and
downstream, category membership gets assigned to a *validated group* of
PRs (extraction/cluster.py's coherence check), never guessed for one PR in
isolation.

This is also the sole basis for what gets embedded (see build_embedding_text
below) -- raw title/diff/comments are deliberately never embedded directly;
they're read once here to produce a compact, comparable representation.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.llm.client import LLMError, complete_json

PROMPT_VERSION = "technique-extract-v1"
BATCH_SIZE = 10

# Comments from these actors are near-always pure status noise (deploy
# previews, coverage-report boilerplate) with no technique content -- worth
# excluding so they don't eat the char budget that real review discussion
# needs. Review bots that actually reason about code (coderabbitai,
# gemini-code-assist, copilot's reviewer, codecov's own analysis text) stay
# in; they regularly carry real signal.
_NOISE_BOT_RE = re.compile(r"^(vercel|netlify\[bot\]|render|now\[bot\])$", re.I)

MAX_BODY_CHARS = 3000
MAX_FILES = 10
MAX_PATCH_CHARS_PER_FILE = 1500
MAX_HUMAN_SIGNAL_CHARS = 800
MAX_COMMENTS_CHARS = 3000
MAX_COMMENTS_COUNT = 15

_VALID_DIRECTIONS = {"positive", "negative", "unclear"}

# Step 1: relevance judgment ONLY -- nothing else. Bundling this into the same
# call as mechanism/resource/phase extraction (the old single-prompt design)
# gave it no room to reason and no verification; it's the highest-stakes
# decision in the pipeline (everything downstream depends on what gets kept)
# so it gets its own dedicated, focused call, run before extraction ever
# touches a record. Forces explicit reasoning before the yes/no, so the
# model can't jump straight to a guess -- but the question itself stays a
# single direct yes/no, not a category taxonomy to classify into.
RELEVANCE_SYSTEM_PROMPT = """You are judging whether a PR's actual code change would move a Core
Web Vitals metric -- LCP, CLS, INP -- or a closely related loading metric: TTFB, FCP, TBT, total
bundle size, or network request count/timing. Not "is this a good PR" or "is this performance-
adjacent in spirit" -- would it measurably move one of these specific metrics.

Read the title, body, diff, and discussion for each PR below. First reason explicitly about what
the diff actually changes and which metric (if any) that would move. Then answer yes or no.

A PR is NOT CWV-motivated just because it touches a file also involved in rendering, or uses
words like "performance"/"optimize" in passing -- the code change itself has to plausibly move
one of those metrics. Docs/demo/site-content changes, chores, branch merges, dependency version
bumps with no behavior change, CI/build/lint config, test-only changes, and backend logic with no
effect on what the browser loads or renders are NOT CWV-motivated, even if their title mentions
performance.

Real examples this judgment has gotten wrong before -- do not repeat these:
- "docs: add Calendar event range demo" -> no (a demo page, doesn't move any metric)
- "site: add componentName for SemanticPreview" -> no (docs-site prop, not a runtime change)
- "Merge up/2.3.x to 2.4.x" -> no (a branch merge, not a code change)
- "chore: merge feature to main" -> no (same)

Return strict JSON, one entry per input, same order:
{"judgments": [{"id": "<source_id>", "reasoning": "<one sentence: what the diff changes and which
  metric it would or wouldn't move>", "cwv_motivated": true|false}]}
Do not omit any input."""

# Step 2: extraction. Only ever called on records step 1 already confirmed
# cwv_motivated -- no drop field here, this call's only job is naming what
# the (already-confirmed-relevant) technique actually is.
SYSTEM_PROMPT = """You are a web-performance analyst extracting objective, checkable facts about
a PR already confirmed to be a genuine performance technique. For each PR record below, read its
title, body, diff, and discussion, then extract:

- technique: short name for the specific mechanism (e.g. "IntersectionObserver lazy-load",
  "dynamic import() code split", "WebP image conversion", "tree-shakeable named exports")
- mechanism: one sentence -- the concrete implementation detail, not a category name
- affected_resource: what the browser loads/renders that this changes -- one of:
  image | font | javascript | css | network | dom | server-response | third-party-script | media
- render_phase: when this matters -- one of: pre-paint | post-paint | interaction | build-time
- description: ONE tight sentence, mechanism-focused (not generic "improves performance")
- direction: ONLY for records with signal_type "perf_flagged" (others have a confirmed direction
  already -- return null for those): "positive" (the change IS the improvement), "negative" (the
  change is a regression, or fixes/is complained about as one), "unclear" (can't confidently tell
  from the diff + discussion -- do not guess)

Return strict JSON -- one entry per input, same order:
{"extractions": [{"id": "<source_id>", "technique": "...", "mechanism": "...",
  "affected_resource": "...", "render_phase": "...", "description": "...",
  "direction": "positive"|"negative"|"unclear"|null}]}
Do not omit any input record."""


@dataclass
class RelevanceJudgment:
    record_id: str
    cwv_motivated: bool
    reasoning: str = ""


@dataclass
class TechniqueExtraction:
    record_id: str
    drop: bool
    relevance_reasoning: str = ""
    technique: str = ""
    mechanism: str = ""
    affected_resource: str = ""
    render_phase: str = ""
    description: str = ""
    direction: str | None = None


def build_embedding_text(e: TechniqueExtraction) -> str:
    """The ONLY text that ever gets embedded for a PR -- the distilled
    extraction, never raw title/diff/comments. Fixed field order, always
    present, so length/format is comparable across every record."""
    return (
        f"Technique: {e.technique}\n"
        f"Mechanism: {e.mechanism}\n"
        f"Affected resource: {e.affected_resource}\n"
        f"Render phase: {e.render_phase}\n"
        f"{e.description}"
    )


def _select_files(files: list[dict]) -> list[dict]:
    """Score by patch length (a config/lockfile diff shouldn't crowd out the
    real code change just by being first in the API's response order)."""
    scored = sorted(files, key=lambda f: len(f.get("patch") or ""), reverse=True)
    return scored[:MAX_FILES]


def _select_comments(comments: list[dict]) -> list[dict]:
    filtered = [c for c in comments if not _NOISE_BOT_RE.match(c.get("author") or "")]
    filtered.sort(key=lambda c: c.get("created_at") or "")
    return filtered[:MAX_COMMENTS_COUNT]


def _compact(record: PRRecord) -> dict:
    files = [
        {"filename": f.get("filename", ""), "patch": (f.get("patch") or "")[:MAX_PATCH_CHARS_PER_FILE]}
        for f in _select_files(record.changed_files)
    ]

    comments_text = []
    budget = MAX_COMMENTS_CHARS
    for c in _select_comments(record.pr_comments or []):
        body = (c.get("body") or "").strip()
        if not body or budget <= 0:
            continue
        entry = f"[{c.get('kind')}/{c.get('author')}] {body[:budget]}"
        comments_text.append(entry)
        budget -= len(entry)

    return {
        "id": record.id,
        "title": record.title or "",
        "signal_type": record.signal_type,
        "human_signal": (record.human_signal_text or "")[:MAX_HUMAN_SIGNAL_CHARS],
        "body": (record.pr_body_markdown or "")[:MAX_BODY_CHARS],
        "discussion": comments_text,
        "files": files,
    }


def _cache_key(record: PRRecord) -> str:
    payload = json.dumps(_compact(record), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{PROMPT_VERSION}:{record.id}:{digest}"


def _load_cache(cache_dir: Path) -> dict[str, TechniqueExtraction]:
    path = cache_dir / "technique_extractions.jsonl"
    if not path.exists():
        return {}
    out: dict[str, TechniqueExtraction] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["cache_key"]] = TechniqueExtraction(**{k: v for k, v in d.items() if k != "cache_key"})
    return out


def _save_cache(entries: list[tuple[str, TechniqueExtraction]], cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "technique_extractions.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for key, e in entries:
            f.write(json.dumps({"cache_key": key, **asdict(e)}) + "\n")


def _call_relevance_batch(batch: list[PRRecord], backend: str, model: str | None, timeout: int) -> list[RelevanceJudgment]:
    user = "Records:\n" + json.dumps(
        [_compact(r) for r in batch], separators=(",", ":"), ensure_ascii=False
    )
    result = complete_json(RELEVANCE_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
    by_id = {item["id"]: item for item in result.get("judgments", [])}

    out = []
    for record in batch:
        item = by_id.get(record.id)
        if item is None:
            # No verdict returned -- never guess relevance, treat as not motivated.
            out.append(RelevanceJudgment(record_id=record.id, cwv_motivated=False))
            continue
        out.append(RelevanceJudgment(
            record_id=record.id,
            cwv_motivated=bool(item.get("cwv_motivated")),
            reasoning=item.get("reasoning") or "",
        ))
    return out


def _call_batch(batch: list[PRRecord], backend: str, model: str | None, timeout: int) -> dict[str, dict]:
    user = "Records:\n" + json.dumps(
        [_compact(r) for r in batch], separators=(",", ":"), ensure_ascii=False
    )
    result = complete_json(SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
    return {item["id"]: item for item in result.get("extractions", [])}


def _run_batched(
    records: list[PRRecord],
    call_fn,
    workers: int,
    label: str,
) -> dict[str, object]:
    """Runs call_fn over records in BATCH_SIZE chunks across a thread pool.
    call_fn(batch, backend, model, timeout) -> list[T] | dict[id, dict], both
    normalized to {record_id: result} here."""
    batches = [records[s:s + BATCH_SIZE] for s in range(0, len(records), BATCH_SIZE)]
    out: dict[str, object] = {}
    completed = 0

    def _process(batch):
        try:
            return call_fn(batch)
        except LLMError as exc:
            print(f"    {label} batch LLM error: {exc}")
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, b): b for b in batches}
        for future in as_completed(futures):
            batch = futures[future]
            result = future.result()
            if isinstance(result, dict):
                out.update(result)
            elif isinstance(result, list):
                for item in result:
                    out[item.record_id] = item
            completed += len(batch)
            print(f"    {label} {completed}/{len(records)}")
    return out


def extract_records(
    records: list[PRRecord],
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
    workers: int = 8,
    cache_dir: Path | None = None,
) -> list[TechniqueExtraction]:
    """Two dedicated passes: (1) relevance judgment ONLY, for every record --
    forced explicit reasoning before the yes/no, its own call so it isn't
    competing for attention with 6 other fields. (2) mechanism/resource/
    phase extraction, only for records (1) confirmed cwv_motivated. A
    record that fails (1) never reaches (2) at all."""
    cache: dict[str, TechniqueExtraction] = _load_cache(cache_dir) if cache_dir else {}

    pending: list[tuple[int, PRRecord, str]] = []
    results: list[TechniqueExtraction | None] = [None] * len(records)

    for i, record in enumerate(records):
        key = _cache_key(record)
        if key in cache:
            results[i] = cache[key]
        else:
            pending.append((i, record, key))

    print(f"  technique-extract: {len(records)} records, "
          f"{len(results) - len(pending)} cached, {len(pending)} to call")

    if not pending:
        return [r for r in results if r is not None]

    pending_records = [r for _, r, _ in pending]

    print(f"  step 1/2: relevance judgment for {len(pending_records)} records")
    relevance_by_id = _run_batched(
        pending_records,
        lambda b: _call_relevance_batch(b, backend, model, timeout),
        workers, "judged",
    )

    motivated_records = [r for r in pending_records if relevance_by_id.get(r.id) and relevance_by_id[r.id].cwv_motivated]
    print(f"  step 1/2 done: {len(motivated_records)}/{len(pending_records)} cwv_motivated, "
          f"proceeding to extraction for those only")

    print(f"  step 2/2: technique extraction for {len(motivated_records)} records")
    extraction_by_id = _run_batched(
        motivated_records,
        lambda b: _call_batch(b, backend, model, timeout),
        workers, "extracted",
    ) if motivated_records else {}

    new_cache_entries: list[tuple[str, TechniqueExtraction]] = []
    for idx, record, cache_key in pending:
        judgment = relevance_by_id.get(record.id)
        if judgment is None or not judgment.cwv_motivated:
            ext = TechniqueExtraction(
                record_id=record.id, drop=True,
                relevance_reasoning=judgment.reasoning if judgment else "",
            )
        else:
            item = extraction_by_id.get(record.id, {})
            direction = item.get("direction")
            if direction not in _VALID_DIRECTIONS:
                direction = None
            ext = TechniqueExtraction(
                record_id=record.id, drop=False,
                relevance_reasoning=judgment.reasoning,
                technique=item.get("technique") or "",
                mechanism=item.get("mechanism") or "",
                affected_resource=item.get("affected_resource") or "",
                render_phase=item.get("render_phase") or "",
                description=item.get("description") or "",
                direction=direction,
            )
        results[idx] = ext
        new_cache_entries.append((cache_key, ext))

    if cache_dir and new_cache_entries:
        _save_cache(new_cache_entries, cache_dir)

    return [r for r in results if r is not None]


def write_jsonl(extractions: list[TechniqueExtraction], path: Path) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for e in extractions:
            f.write(json.dumps(asdict(e)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[TechniqueExtraction]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            out.append(TechniqueExtraction(**json.loads(line)))
    return out
