"""LLM backend for stages 2/4/6 (extract/classify/generate) -- every one of
these makes a single "structured JSON (or markdown, for stage 6) out" chat
completion.

`openai` is the only backend this pipeline actually uses: the real OpenAI
API, `OPENAI_API_KEY`/`OPENAI_MODEL` from a root `.env` (`gpt-5.4-mini` by
default -- picked after `gpt-5.4-nano` measurably underperformed on the
extraction/classification judgment task, see docs/pipeline-design.md).

Two other backend implementations exist in this file (`claude-cli`,
`openai-compatible`) and remain selectable via `--backend` for anyone who
wants them, but nothing here defaults to them. `claude-cli` in particular
was tried first and dropped: `claude -p` in a Claude Code sandbox isn't a
stateless completion call, it's a filesystem-aware agentic session, and it
corrupted stage-6 output by reasoning about file permissions / commenting on
files it "noticed" already existed on disk rather than just returning text.
`openai-compatible` stays as unused-but-available parity with smol-planner's
own vllm/Azure path."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    # Load .env from repo root, same "load before anything else" convention
    # smol-planner's training scripts use.
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
            break
    _ENV_LOADED = True


class LLMError(RuntimeError):
    pass


def _with_retry(fn, retries: int = 4):
    """Retries on transient network/server errors (connection blips, 5xx,
    429, timeouts) with exponential backoff -- observed live this session
    (HTTP/2 stream-cancel, HTTP 504) crashing a whole batch for what turned
    out to be a one-off hiccup. Does NOT retry a clear 4xx client error
    (bad request, auth failure) -- retrying that just wastes time on
    something a retry can't fix."""
    import time as _time
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = exc.response.text[:300] if exc.response is not None else ""
            if status is not None and 400 <= status < 500 and status != 429:
                # Not retryable (bad request, auth, etc.) -- but still wrap as
                # LLMError so callers' `except LLMError` actually catches it,
                # per complete_json/complete_text's documented contract.
                raise LLMError(f"HTTP {status}: {body}") from exc
            last_err = exc
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_err = exc
        if attempt < retries - 1:
            _time.sleep(2 ** attempt)
    raise LLMError(f"request failed after {retries} attempts: {last_err}") from last_err


def _call_openai(system: str, user: str, model: str | None, timeout: int) -> str:
    _ensure_env_loaded()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY not set (add it to .env or export it) -- see .env.example")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_openai_compatible(system: str, user: str, base_url: str, api_key: str, model: str, timeout: int) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_claude_cli(system: str, user: str, timeout: int) -> str:
    prompt = f"{system}\n\n{user}\n\nRespond with strict JSON only, no markdown fencing, no commentary."
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMError(f"claude -p timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise LLMError(f"claude -p failed: {proc.stderr[:500]}")
    return proc.stdout.strip()


def _extract_json(text: str) -> dict:
    """claude -p's text output isn't guaranteed to be bare JSON (may wrap it
    in a code fence or add a sentence) -- extract the first {...} block."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"no JSON object found in LLM output: {text[:300]!r}")
    return json.loads(text[start:end + 1])


def complete_json(
    system: str, user: str, *, backend: str = "openai", model: str | None = None,
    base_url: str | None = None, api_key: str | None = None, timeout: int = 120,
) -> dict:
    """Runs one structured-JSON chat completion and returns the parsed dict.
    Raises LLMError on any failure -- callers decide whether to skip/retry."""
    _ensure_env_loaded()
    if backend == "openai":
        raw = _with_retry(lambda: _call_openai(system, user, model, timeout))
    elif backend == "claude-cli":
        raw = _call_claude_cli(system, user, timeout)
    elif backend == "openai-compatible":
        base_url = base_url or os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
        api_key = api_key or os.environ.get("LLM_API_KEY", "EMPTY")
        model = model or os.environ.get("LLM_MODEL_NAME", "")
        raw = _with_retry(lambda: _call_openai_compatible(system, user, base_url, api_key, model, timeout))
    else:
        raise LLMError(f"unknown backend {backend!r}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json(raw)


def complete_text(
    system: str, user: str, *, backend: str = "openai", model: str | None = None,
    base_url: str | None = None, api_key: str | None = None, timeout: int = 180,
) -> str:
    """Like complete_json but for stage 6, which produces markdown, not JSON --
    same three backends, no JSON parsing/response_format constraint."""
    _ensure_env_loaded()
    if backend == "openai":
        api_key_ = os.environ.get("OPENAI_API_KEY")
        if not api_key_:
            raise LLMError("OPENAI_API_KEY not set (add it to .env or export it) -- see .env.example")
        model = model or os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

        def _do():
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key_}"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": 0.2,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        return _with_retry(_do)
    elif backend == "claude-cli":
        return _call_claude_cli_text(system, user, timeout)
    elif backend == "openai-compatible":
        base_url = base_url or os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
        api_key = api_key or os.environ.get("LLM_API_KEY", "EMPTY")
        model = model or os.environ.get("LLM_MODEL_NAME", "")

        def _do():
            resp = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": 0.2,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        return _with_retry(_do)
    raise LLMError(f"unknown backend {backend!r}")


def _call_claude_cli_text(system: str, user: str, timeout: int) -> str:
    prompt = f"{system}\n\n{user}"
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMError(f"claude -p timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise LLMError(f"claude -p failed: {proc.stderr[:500]}")
    return proc.stdout.strip()


def resolve_default_backend() -> str:
    """OpenAI only. `claude-cli` was tried first (no extra credentials
    needed in a Claude Code sandbox) but dropped for two confirmed-live
    reasons: (1) `claude -p` in this environment isn't a stateless
    completion call -- it spawns a filesystem-aware agentic session that
    sometimes reasons about file permissions or comments on files it
    "noticed" already exist, corrupting stage-6 output; (2) it makes the
    pipeline dependent on a Claude Code sandbox rather than a portable API
    key. `claude-cli`/`openai-compatible` remain valid --backend values for
    anyone who wants them, but nothing in this pipeline selects them by
    default anymore."""
    _ensure_env_loaded()
    if not os.environ.get("OPENAI_API_KEY"):
        raise LLMError("OPENAI_API_KEY not set -- add it to .env (see .env.example). This pipeline requires it; there is no fallback backend.")
    return "openai"
