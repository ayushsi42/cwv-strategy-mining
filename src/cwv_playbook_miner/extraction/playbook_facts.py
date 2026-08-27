"""Stage 1.5: extract the same {technique, mechanism, affected_resource,
render_phase, description} shape from the 20 curated playbooks, once, so
routing (stage 2) compares two PRs' worth of the *same kind* of text
against each other instead of a PR's terse extraction against a playbook's
design-doc prose. Only 20 items -- cheap, no batching needed, no cache
needed (rerun is trivial)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from cwv_playbook_miner.llm.client import complete_json
from cwv_playbook_miner.extraction.technique_extract import build_embedding_text

SYSTEM_PROMPT = """You are extracting the same objective, checkable facts from a curated CWV
playbook document that would be extracted from a single PR implementing its technique:

- technique: short name for the specific mechanism this playbook teaches
- mechanism: one sentence -- the concrete implementation detail
- affected_resource: one of: image | font | javascript | css | network | dom | server-response |
  third-party-script | media
- render_phase: one of: pre-paint | post-paint | interaction | build-time
- description: ONE tight sentence, mechanism-focused

Return strict JSON, one entry per input playbook, same order:
{"playbooks": [{"issue_type": "...", "technique": "...", "mechanism": "...",
  "affected_resource": "...", "render_phase": "...", "description": "..."}]}"""


@dataclass
class PlaybookFacts:
    issue_type: str
    technique: str = ""
    mechanism: str = ""
    affected_resource: str = ""
    render_phase: str = ""
    description: str = ""


def _compact_playbook(md_path: Path) -> dict:
    content = md_path.read_text(encoding="utf-8")
    metric_line = ""
    m = re.search(r"\*\*CWV metric:\*\*\s*([^\n]+)", content)
    if m:
        metric_line = m.group(1).strip()
    return {"issue_type": md_path.stem, "metric": metric_line, "content": content[:6000]}


def extract_playbook_facts(
    handoff_dir: Path,
    *,
    backend: str = "openai",
    model: str | None = None,
    timeout: int = 180,
) -> dict[str, PlaybookFacts]:
    md_paths = sorted(p for p in handoff_dir.glob("*.md") if not p.name.startswith("_"))
    if not md_paths:
        return {}

    payload = [_compact_playbook(p) for p in md_paths]
    user = json.dumps({"playbooks": payload}, ensure_ascii=False)
    result = complete_json(SYSTEM_PROMPT, user, backend=backend, model=model, timeout=timeout)
    by_id = {item["issue_type"]: item for item in result.get("playbooks", [])}

    out: dict[str, PlaybookFacts] = {}
    for p in md_paths:
        issue_type = p.stem
        item = by_id.get(issue_type, {})
        out[issue_type] = PlaybookFacts(
            issue_type=issue_type,
            technique=item.get("technique") or "",
            mechanism=item.get("mechanism") or "",
            affected_resource=item.get("affected_resource") or "",
            render_phase=item.get("render_phase") or "",
            description=item.get("description") or "",
        )
    return out


def write_jsonl(facts: dict[str, PlaybookFacts], path: Path) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        for pf in facts.values():
            f.write(json.dumps(asdict(pf)) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: Path) -> dict[str, PlaybookFacts]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["issue_type"]] = PlaybookFacts(**d)
    return out


__all__ = ["PlaybookFacts", "extract_playbook_facts", "write_jsonl", "read_jsonl", "build_embedding_text"]
