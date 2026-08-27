"""Stage 1b/c: text embedding + cosine routing.

Three embedding providers, all returning L2-normalised float32 arrays so
cosine similarity reduces to a dot product:

  openai               — text-embedding-3-small via OpenAI API (default)
  openai-compatible    — same HTTP contract, any base_url (vllm, ollama,
                         LM Studio, etc.) — drop-in for GPU-local models
  sentence-transformers — fully local HuggingFace model, no API key needed
                          (import is lazy so the package is optional)

The `route_summaries` function assigns each summary to "existing" (matched an
existing playbook), "novel" (no close match, goes to HDBSCAN clustering), or
"drop" (already DROP from the summarise step, or below the low threshold).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import requests

from dotenv import load_dotenv

if TYPE_CHECKING:
    pass

_ENV_LOADED = False

EMBED_MODEL_OPENAI = "text-embedding-3-small"

# Route thresholds (cosine similarity against nearest playbook embedding).
# Calibrate empirically on a labelled sample; these are good starting values.
HIGH_THRESHOLD = 0.78   # above → route to EXISTING playbook
LOW_THRESHOLD  = 0.45   # below → route to NOVEL pool


def _ensure_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[4] / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
            break
    _ENV_LOADED = True


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _embed_openai(
    texts: list[str],
    model: str,
    api_key: str,
    timeout: int,
) -> np.ndarray:
    resp = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "input": texts},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    arr = np.array([d["embedding"] for d in data], dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def _embed_openai_compatible(
    texts: list[str],
    model: str,
    base_url: str,
    api_key: str,
    timeout: int,
) -> np.ndarray:
    resp = requests.post(
        f"{base_url.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "input": texts},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    arr = np.array([d["embedding"] for d in data], dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def _embed_sentence_transformers(texts: list[str], model: str) -> np.ndarray:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        ) from exc
    st_model = SentenceTransformer(model)
    arr = st_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(arr, dtype=np.float32)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def embed_texts(
    texts: list[str],
    *,
    provider: str = "openai",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int = 60,
    batch_size: int = 512,
) -> np.ndarray:
    """Embed a list of texts and return an (N, D) float32 array of unit vectors.

    For large lists the request is split into batches of `batch_size` to stay
    within API token limits.
    """
    _ensure_env()

    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start:start + batch_size]

        if provider == "openai":
            key = api_key or os.environ.get("OPENAI_API_KEY", "")
            m = model or os.environ.get("OPENAI_EMBED_MODEL", EMBED_MODEL_OPENAI)
            chunks.append(_embed_openai(chunk, m, key, timeout))

        elif provider == "openai-compatible":
            url = base_url or os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
            key = api_key or os.environ.get("LLM_API_KEY", "EMPTY")
            m = model or os.environ.get("LLM_EMBED_MODEL", "nomic-embed-text")
            chunks.append(_embed_openai_compatible(chunk, m, url, key, timeout))

        elif provider == "sentence-transformers":
            m = model or os.environ.get("ST_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
            chunks.append(_embed_sentence_transformers(chunk, m))

        else:
            raise ValueError(f"Unknown embed provider {provider!r}. "
                             "Choose: openai | openai-compatible | sentence-transformers")

    return np.vstack(chunks)


def embed_playbooks(
    handoff_dir: Path,
    **embed_kwargs,
) -> dict[str, np.ndarray]:
    """Return {issue_type: unit_vector} for every *.md in handoff_dir (excluding _FORMAT.md).

    Each playbook is embedded using its "What this addresses" section + the
    issue_type identifier + CWV metric line — just the semantically dense part,
    not the full text.
    """
    import re

    result: dict[str, np.ndarray] = {}
    texts: list[str] = []
    issue_types: list[str] = []

    for md_path in sorted(handoff_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue
        issue_type = md_path.stem
        content = md_path.read_text(encoding="utf-8")

        # Pull the metric line from the callout and the What-this-addresses section
        metric_line = ""
        m = re.search(r"\*\*CWV metric:\*\*\s*([^\n]+)", content)
        if m:
            metric_line = m.group(1).strip()

        what_section = ""
        m2 = re.search(r"## What this addresses\n+([\s\S]+?)(?=\n## )", content)
        if m2:
            what_section = m2.group(1).strip()[:600]

        text = f"{issue_type}: {metric_line}. {what_section}"
        texts.append(text)
        issue_types.append(issue_type)

    if not texts:
        return {}

    embeddings = embed_texts(texts, **embed_kwargs)
    for issue_type, vec in zip(issue_types, embeddings):
        result[issue_type] = vec
    return result


def route_summaries(
    summaries: list[str],
    playbook_embeddings: dict[str, np.ndarray],
    *,
    high_threshold: float = HIGH_THRESHOLD,
    low_threshold: float = LOW_THRESHOLD,
    **embed_kwargs,
) -> list[tuple[str, str | None, float]]:
    """Route each summary to ("existing", playbook_id, score) |
    ("novel", None, score) | ("drop", None, score).

    Assumes summaries already marked DROP by the LLM summariser have been
    filtered out before calling this — pass only non-drop summaries.
    """
    if not summaries or not playbook_embeddings:
        return [("novel", None, 0.0)] * len(summaries)

    summary_vecs = embed_texts(summaries, **embed_kwargs)

    playbook_ids = list(playbook_embeddings.keys())
    playbook_matrix = np.stack([playbook_embeddings[pid] for pid in playbook_ids])  # (P, D)

    # Cosine similarity = dot product (both sides are unit vectors)
    sims = summary_vecs @ playbook_matrix.T  # (N, P)

    routes = []
    for i, row in enumerate(sims):
        best_idx = int(np.argmax(row))
        score = float(row[best_idx])
        best_playbook = playbook_ids[best_idx]

        if score >= high_threshold:
            routes.append(("existing", best_playbook, score))
        elif score < low_threshold:
            routes.append(("novel", None, score))
        else:
            # Middle band — return as "ambiguous" for LLM disambiguation
            routes.append(("ambiguous", best_playbook, score))

    return routes


def disambiguate_ambiguous(
    ambiguous_summaries: list[str],
    candidate_playbook_ids: list[str],
    playbook_descriptions: dict[str, str],
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 60,
) -> list[tuple[str, str | None]]:
    """For summaries in the ambiguous band, ask the LLM to decide existing vs novel.

    Returns list of ("existing", playbook_id) | ("novel", None).
    """
    import json as _json
    from cwv_playbook_miner.llm.client import complete_json

    if not ambiguous_summaries:
        return []

    playbook_list = "\n".join(
        f"- {pid}: {playbook_descriptions.get(pid, pid)}"
        for pid in candidate_playbook_ids
    )
    system = (
        "You are routing web-performance technique summaries to an existing playbook "
        "or flagging them as novel (no existing playbook covers them).\n\n"
        f"Existing playbooks:\n{playbook_list}\n\n"
        "For each summary, return the best matching playbook_id if the technique is "
        "clearly an instance of that issue type, or null if it's genuinely novel.\n"
        'Return JSON: {"routes": [{"summary": "...", "playbook_id": "<id or null>"}]}'
    )
    user = _json.dumps({"summaries": ambiguous_summaries})
    result = complete_json(system, user, backend=backend, model=model, timeout=timeout)

    routes = []
    for item in result.get("routes", []):
        pid = item.get("playbook_id")
        routes.append(("existing" if pid else "novel", pid))
    # Pad if model returned fewer items
    while len(routes) < len(ambiguous_summaries):
        routes.append(("novel", None))
    return routes
