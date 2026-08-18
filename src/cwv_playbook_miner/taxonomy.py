"""Stable parent strategy taxonomy for hierarchical technique mining."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cwv_playbook_miner.extraction.pattern_extract import ExtractedPattern


PARENT_STRATEGIES = {
    "javascript-delivery": "JavaScript delivery and loading",
    "main-thread-computation": "Main-thread computation",
    "interaction-responsiveness": "Interaction responsiveness",
    "rendering-and-hydration": "Rendering and hydration",
    "layout-stability": "Layout stability",
    "image-delivery": "Image delivery",
    "font-delivery": "Font delivery",
    "css-delivery": "CSS delivery",
    "resource-prioritization": "Critical-resource prioritization",
    "network-payload": "Network payload reduction",
    "cache-and-data-reuse": "Cache and data reuse",
    "server-response": "Server response latency",
    "third-party-cost": "Third-party cost",
    "dom-complexity": "DOM and rendering complexity",
    "media-and-embeds": "Media and embedded content",
}


def parent_taxonomy_prompt() -> str:
    return "\n".join(f'- "{key}": {label}' for key, label in PARENT_STRATEGIES.items())


def write_parent_proposals(patterns: list["ExtractedPattern"], path: Path) -> int:
    """Persist unsupported parent proposals without auto-expanding taxonomy."""
    grouped: dict[tuple[str, str], list["ExtractedPattern"]] = defaultdict(list)
    for pattern in patterns:
        if pattern.parent_strategy != "unclassified":
            continue
        parent = re.sub(r"\s+", " ", pattern.proposed_parent_strategy.strip().lower())
        sub = re.sub(r"\s+", " ", pattern.sub_strategy.strip().lower())
        if parent and sub:
            grouped[(parent, sub)].append(pattern)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for (parent, sub), items in sorted(grouped.items()):
            repos = sorted({item.source_repo for item in items})
            handle.write(json.dumps({
                "proposed_parent_strategy": parent,
                "proposed_sub_strategy": sub,
                "observation_count": len(items),
                "distinct_repo_count": len(repos),
                "source_prs": sorted({item.source_id for item in items}),
                "promotion_ready": len(items) >= 3 and len(repos) >= 2,
                "status": "human-review",
            }) + "\n")
    return len(grouped)
