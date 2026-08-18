"""Adapter for a real, pre-mined external PR corpus (`Ayush-Singh/
cwv-planner-dataset-v1` on HuggingFace, private -- needs `HF_TOKEN` in
`.env`), used as a *second* input channel alongside this pipeline's own live
GH Archive mining (sourcing/gharchive_mine.py).

Why this exists: live mining's own perf_improvement yield was confirmed
near-zero (0 records) across ~52 real days scanned (two independent windows,
264h and 620h, both after two real bugfixes -- see docs/pipeline-design.md).
`perf_decrease` fared better (2-4 real records per window) via the same
mechanism. The external corpus's `golden.jsonl` (656 rows) was built via the
*same* discovery mechanism (GH Archive bot-comment discovery, not keyword
search) by a separate pipeline, just run at far greater historical depth --
same provenance standard, much larger pool. Every record keeps its real
`repo#pr_number` id and real diff, so "grounded in real source PRs" still
holds; `source` on each `PRRecord` marks exactly which came from where.

Not a replacement for live mining -- `perf_decrease`/anti-pattern grounding
still comes from this pipeline's own mining, since the external corpus is
perf_improvement-only.
"""

from __future__ import annotations

import os

from cwv_playbook_miner.extraction.pr_record import PRRecord

GOLDEN_REPO_ID = "Ayush-Singh/cwv-planner-dataset-v1"
GOLDEN_FILENAME = "data/golden.jsonl"


def _hf_download(filename: str) -> str:
    from huggingface_hub import hf_hub_download

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not set (add it to .env) -- needed to access the private external corpus")
    return hf_hub_download(repo_id=GOLDEN_REPO_ID, filename=filename, repo_type="dataset", token=token)


# Confirmed live: selecting golden.jsonl purely by delta magnitude surfaces
# almost entirely dependency bumps / refactors / unrelated features (e.g.
# "chore(deps): update dependency @types/node", "chore(monorepo): upgrade
# to Lerna v9") -- large Lighthouse swings that are very plausibly measurement
# noise or incidental correlation, exactly what smol-planner's own
# cwv_pr_enrichment.py judge stage exists to filter (its
# `is_performance_motivated` / `primary_category` fields). This pipeline
# doesn't have that separate judge stage, so the cheaper fix is requiring
# actual performance intent in the title/body up front, not the delta alone.
_INTENT_KEYWORDS = (
    "lazy", "defer", "preload", "prefetch", "bundle", "image", "compress",
    "cache", "render-block", "render block", "critical css", "webp", "avif",
    "minif", "code-split", "code split", "tree-shak", "priority", "lighthouse",
    "perf", "optimi", "cls", "lcp", "ttfb", "inp", "fcp", "core web vital",
    "web vital", "font-display", "font display",
)


def _has_performance_intent(title: str, body: str) -> bool:
    text = f"{title or ''} {body or ''}".lower()
    return any(k in text for k in _INTENT_KEYWORDS)


def _title_has_performance_intent(title: str) -> bool:
    # Stronger signal than a body-only mention -- confirmed live that
    # requiring it in the TITLE surfaces clearly-intentional PRs
    # (koutyuke.dev#20 "perf(web): improve lighthouse performance score",
    # toast-stats#590 "fix(perf): ... drops CLS 0.217 -> 0.01") ahead of
    # title-generic PRs that only happen to mention a keyword in the body.
    return any(k in (title or "").lower() for k in _INTENT_KEYWORDS)


def load_golden_perf_improvement(
    min_perf_delta: float = 15.0, limit: int | None = None, require_intent: bool = True,
) -> list[PRRecord]:
    """Loads golden.jsonl, filters to a real, meaningful performance delta
    (default 15.0 -- stricter than live mining's 5.0 threshold, since this
    corpus is large enough to afford being choosier and stage-2 extraction
    is one LLM call per record, so keeping volume sane matters), and maps
    into this pipeline's own PRRecord shape. `require_intent` (default True)
    additionally requires actual performance-related language in the title/
    body -- see the module-level note above on why delta alone isn't enough."""
    import json

    path = _hf_download(GOLDEN_FILENAME)
    records: list[PRRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = json.loads(line)
            delta = raw.get("metrics", {}).get("score_delta", {}).get("performance")
            if not isinstance(delta, (int, float)) or delta < min_perf_delta:
                continue
            if require_intent and not _has_performance_intent(raw.get("title", ""), raw.get("pr_body_markdown", "")):
                continue
            scores_before = raw.get("metrics", {}).get("scores_before", {})
            scores_after = raw.get("metrics", {}).get("scores_after", {})
            records.append(PRRecord(
                id=raw["id"], repo=raw["repo"], pr_number=raw["pr_number"],
                signal_type=raw.get("signal_type", "perf_improvement"),
                metric_key="performance",
                before=scores_before.get("performance"), after=scores_after.get("performance"), delta=delta,
                title=raw.get("title"), pr_body_markdown=raw.get("pr_body_markdown"),
                changed_files=[
                    {"filename": cf["filename"], "patch": cf.get("patch", "")}
                    for cf in raw.get("changed_files", [])
                ],
                template_names=["external:cwv-planner-dataset-v1/golden"],
                source="external:cwv-planner-dataset-v1/golden",
            ))
    # Title-level intent match first (strongest signal), then by delta --
    # not delta alone, see the module-level note on why that surfaces noise.
    records.sort(key=lambda r: (_title_has_performance_intent(r.title), r.delta or 0), reverse=True)
    return records[:limit] if limit else records
