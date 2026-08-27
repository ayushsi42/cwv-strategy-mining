"""Text embedding, used by routing (stage 2) and clustering (stage 3) to
compare the distilled per-PR/per-playbook facts from technique_extract.py /
playbook_facts.py -- never raw title/diff/comments directly.

Three providers, all returning L2-normalised float32 arrays so cosine
similarity reduces to a dot product:

  openai               — text-embedding-3-small via OpenAI API (default)
  openai-compatible    — same HTTP contract, any base_url (Azure, vLLM,
                         ollama, LM Studio, etc.)
  sentence-transformers — fully local HuggingFace model, no API key needed
                          (import is lazy so the package is optional)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

_ENV_LOADED = False

EMBED_MODEL_OPENAI = "text-embedding-3-small"


def _ensure_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
            break
    _ENV_LOADED = True


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _embed_openai(texts: list[str], model: str, api_key: str, timeout: int) -> np.ndarray:
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


def _embed_openai_compatible(texts: list[str], model: str, base_url: str, api_key: str, timeout: int) -> np.ndarray:
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
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
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
