"""Stage 2 (redesign): retrieve-then-verify routing.

Replaces the raw cosine-threshold routing in triage/embed.py. Embedding
similarity only ever narrows each PR to its top-K candidate playbooks (a
fast pre-filter) -- the actual existing/novel decision is always a real LLM
judgment against the candidates' full text, never a bare number. A record
only skips the LLM call when even its best candidate is obviously nowhere
close (pure cost shortcut on the unambiguous end; the boundary always gets
a real judgment).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from cwv_playbook_miner.extraction.pr_record import PRRecord
from cwv_playbook_miner.extraction.technique_extract import TechniqueExtraction, build_embedding_text
from cwv_playbook_miner.extraction.playbook_facts import PlaybookFacts
from cwv_playbook_miner.llm.client import LLMError, complete_json
from cwv_playbook_miner.embedding import embed_texts

TOP_K = 3
NO_MATCH_FLOOR = 0.35  # below this even for the best candidate -> auto-novel, no LLM call
VERIFY_BATCH_SIZE = 6
PLAYBOOK_EXCERPT_CHARS = 5000

VERIFY_SYSTEM_PROMPT = """You are deciding, for each PR below, whether it is a genuine instance of one
of its candidate playbooks' technique, or something novel those playbooks don't cover.

Rules:
- A PR only matches a candidate playbook if it implements essentially the SAME technique -- same
  mechanism, same affected resource. Superficial vocabulary overlap ("reduces size", "improves
  loading") is NOT enough on its own.
- If a PR only partially overlaps a candidate (e.g. touches the same resource type via a
  different mechanism), prefer "novel" -- false negatives (missing an enrichment) are cheaper
  than false positives (diluting a playbook's evidence with a different technique).
- Only pick a playbook_id that was actually listed as one of that PR's candidates.

Return strict JSON, one entry per input PR, same order:
{"routes": [{"id": "<pr id>", "route": "existing"|"novel", "playbook_id": "<id or null>",
  "rationale": "<one sentence>"}]}"""


@dataclass
class RoutingRecord:
    record_id: str
    route: str  # "existing" | "novel" | "drop"
    playbook_id: str | None = None
    rationale: str = ""
    top_candidates: list[str] = field(default_factory=list)
    top_score: float = 0.0


def _load_playbook_texts(handoff_dir: Path, issue_types: list[str]) -> dict[str, str]:
    out = {}
    for it in issue_types:
        p = handoff_dir / f"{it}.md"
        if p.exists():
            out[it] = p.read_text(encoding="utf-8")[:PLAYBOOK_EXCERPT_CHARS]
    return out


def _verify_batch(
    batch: list[tuple[PRRecord, TechniqueExtraction, list[str], float]],
    playbook_texts: dict[str, str],
    backend: str, model: str | None, timeout: int,
) -> dict[str, tuple[str, str | None, str]]:
    """Returns {record_id: (route, playbook_id, rationale)}."""
    candidate_ids = sorted({pid for _, _, cands, _ in batch for pid in cands})
    playbooks_payload = [
        {"issue_type": pid, "content": playbook_texts.get(pid, "")}
        for pid in candidate_ids
    ]
    prs_payload = []
    for pr, ext, cands, _ in batch:
        prs_payload.append({
            "id": pr.id,
            "candidates": cands,
            "extracted_technique": ext.technique,
            "extracted_mechanism": ext.mechanism,
            "affected_resource": ext.affected_resource,
            "title": pr.title or "",
            "human_signal": (pr.human_signal_text or "")[:400],
        })
    user = json.dumps({"candidate_playbooks": playbooks_payload, "prs": prs_payload}, ensure_ascii=False)
    result = complete_json(VERIFY_SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)

    out = {}
    for item in result.get("routes", []):
        rid = item.get("id")
        route = item.get("route")
        pid = item.get("playbook_id")
        if route == "existing" and pid not in candidate_ids:
            # Not a real candidate -- the model hallucinated an id. Don't trust it.
            route, pid = "novel", None
        out[rid] = (route or "novel", pid if route == "existing" else None, item.get("rationale", ""))
    return out


def _cache_path(cache_dir: Path) -> Path:
    return cache_dir / "route_verify.jsonl"


def _load_verify_cache(cache_dir: Path) -> dict[str, RoutingRecord]:
    path = _cache_path(cache_dir)
    if not path.exists():
        return {}
    out: dict[str, RoutingRecord] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["record_id"]] = RoutingRecord(**d)
    return out


def _append_verify_cache(records: list[RoutingRecord], cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    with _cache_path(cache_dir).open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")


def route_records(
    records: list[PRRecord],
    extractions: dict[str, TechniqueExtraction],
    playbook_facts: dict[str, PlaybookFacts],
    handoff_dir: Path,
    *,
    embed_provider: str = "openai",
    embed_model: str | None = None,
    embed_base_url: str | None = None,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
    cache_dir: Path | None = None,
) -> list[RoutingRecord]:
    non_drop = [r for r in records if r.id in extractions and not extractions[r.id].drop]
    dropped_ids = {r.id for r in records if r.id not in extractions or extractions[r.id].drop}

    results: list[RoutingRecord] = [
        RoutingRecord(record_id=rid, route="drop") for rid in dropped_ids
    ]
    if not non_drop:
        return results

    print(f"[route] embedding {len(non_drop)} PR extractions + {len(playbook_facts)} playbooks...")
    pr_texts = [build_embedding_text(extractions[r.id]) for r in non_drop]
    pr_vecs = embed_texts(pr_texts, provider=embed_provider, model=embed_model, base_url=embed_base_url)

    playbook_ids = list(playbook_facts.keys())
    playbook_texts_embed = [build_embedding_text(playbook_facts[pid]) for pid in playbook_ids]
    playbook_vecs = embed_texts(playbook_texts_embed, provider=embed_provider, model=embed_model, base_url=embed_base_url)

    sims = pr_vecs @ playbook_vecs.T  # (N, P)

    to_verify: list[tuple[PRRecord, TechniqueExtraction, list[str], float]] = []
    auto_novel = 0
    for i, r in enumerate(non_drop):
        row = sims[i]
        top_idx = np.argsort(row)[::-1][:TOP_K]
        top_score = float(row[top_idx[0]])
        cands = [playbook_ids[j] for j in top_idx]
        if top_score < NO_MATCH_FLOOR:
            results.append(RoutingRecord(record_id=r.id, route="novel", top_candidates=cands, top_score=top_score))
            auto_novel += 1
        else:
            to_verify.append((r, extractions[r.id], cands, top_score))

    verify_cache = _load_verify_cache(cache_dir) if cache_dir else {}
    still_pending = []
    for item in to_verify:
        r = item[0]
        cached = verify_cache.get(r.id)
        if cached is not None:
            results.append(cached)
        else:
            still_pending.append(item)
    to_verify = still_pending

    print(f"[route] {auto_novel} auto-novel (below {NO_MATCH_FLOOR} floor), "
          f"{len(verify_cache)} cached, {len(to_verify)} to verify via LLM")

    handoff_texts = _load_playbook_texts(handoff_dir, playbook_ids)

    batches = [to_verify[s:s + VERIFY_BATCH_SIZE] for s in range(0, len(to_verify), VERIFY_BATCH_SIZE)]
    verified = 0
    for batch in batches:
        try:
            decisions = _verify_batch(batch, handoff_texts, backend, model, timeout)
        except LLMError as exc:
            print(f"    verify batch LLM error: {exc} -- marking as novel")
            decisions = {}
        batch_results = []
        for pr, ext, cands, top_score in batch:
            route, pid, rationale = decisions.get(pr.id, ("novel", None, ""))
            batch_results.append(RoutingRecord(
                record_id=pr.id, route=route, playbook_id=pid, rationale=rationale,
                top_candidates=cands, top_score=top_score,
            ))
        results.extend(batch_results)
        if cache_dir:
            _append_verify_cache(batch_results, cache_dir)
        verified += len(batch)
        print(f"    verified {verified}/{len(to_verify)}")

    return results


def write_jsonl(records: list[RoutingRecord], path: Path) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> list[RoutingRecord]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            out.append(RoutingRecord(**json.loads(line)))
    return out
