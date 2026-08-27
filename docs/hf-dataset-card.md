---
license: mit
language:
- en
task_categories:
- text-classification
- text-generation
tags:
- web-performance
- core-web-vitals
- github
- software-engineering
pretty_name: CWV Strategy Mining Dataset
---

# CWV Strategy Mining Dataset

Real, merged GitHub PRs mined for measured Core Web Vitals (CWV)
techniques, plus every intermediate pipeline artifact through final
generated playbook candidates. Produced by
[cwv-playbook-miner](https://github.com/ayushsi42/cwv-strategy-mining),
scanning the full public GH Archive event stream. Every decision in the
pipeline runs on real PR text (title, body, diff, comments, reviews) — never
a short phrase, never a bare similarity threshold. See the repo's
`SESSION_NOTES.md` for the full chronological design log: what was found,
why each fix was made, and what it was verified against.

![pipeline flow](docs/pipeline-flow.svg)

## Why

Automated Lighthouse/bundle-size bots are the obvious place to find
before/after performance numbers on a PR, but they're a small fraction of
real performance-motivated PRs — most authors and reviewers never run one.
This dataset combines that narrow, precisely-measured bot signal with a
much larger pool of PRs where a human reviewer (or another automated tool)
mentioned performance in plain text, with no bot-parsed number required.

## Contents

| Folder | Files | What it is |
|---|---|---|
| `source/` | `perf_improvement.jsonl`, `perf_decrease.jsonl`, `perf_flagged.jsonl` | Raw mined PR records — repo, PR number, signal type, bot-parsed metric (when available), title, body, diff patches, and every issue comment/review/inline review comment backfilled via GitHub GraphQL |
| `patterns/` | `extractions.jsonl` | Per-PR technique extraction: `technique`, `mechanism`, `affected_resource`, `render_phase`, `description`, inferred `direction` (for human-flagged PRs) — only for PRs that passed the CWV-relevance gate |
| `aggregation/` | `routing.jsonl`, `novel_clusters.jsonl`, `enrichments.jsonl`, `playbook_facts.jsonl` | Routing decisions (existing playbook match vs. novel), coherence-verified novel-technique clusters, diversity-weighted existing-playbook evidence, and the same fact-shape extracted from the 20 curated playbooks |
| `playbooks/new_playbooks/` | 9 `.md` files | Full new `{issue_type}.md` candidates — front matter includes `source_prs`, draft → critic → grounding-checked → AEM-fidelity-checked |
| `playbooks/enriched/` | 17 `.enrichment.md` files | New approach/anti-pattern subsection(s) for an existing playbook — no front matter (spliced body content), grounding noted via a `> **Source PRs**` line instead |

### `source/*.jsonl` schema

```json
{
  "id": "repo#pr_number",
  "repo": "owner/repo",
  "pr_number": 123,
  "signal_type": "perf_improvement | perf_decrease | perf_flagged",
  "metric_key": "performance | lcp_ms | cls | ... | null",
  "before": 70.0, "after": 88.0, "delta": 18.0,
  "title": "PR title",
  "pr_body_markdown": "...",
  "changed_files": [{"filename": "...", "patch": "..."}],
  "pr_comments": [{"kind": "issue_comment|review|review_comment", "author": "...", "body": "...", "created_at": "...", "state": "...", "path": "..."}],
  "text_enriched": true, "text_truncated": false,
  "merged_at": "2025-01-01T00:00:00Z",
  "human_signal_text": "the flagging review/comment text (perf_flagged only)"
}
```

`title`/`pr_body_markdown`/`pr_comments` are backfilled via GitHub's
GraphQL API (`enrich-pr-text` + `refetch-truncated`) — GH Archive's free
event stream never carries them. `perf_flagged` records have
`metric_key`/`before`/`after`/`delta` all `null` (no bot template matched
them); `human_signal_text` carries the comment that triggered discovery.

### `patterns/extractions.jsonl` schema

```json
{
  "record_id": "repo#pr_number", "drop": false,
  "relevance_reasoning": "...",
  "technique": "...", "mechanism": "...",
  "affected_resource": "image|font|javascript|css|network|dom|server-response|third-party-script|media",
  "render_phase": "pre-paint|post-paint|interaction|build-time",
  "description": "...", "direction": "positive|negative|unclear|null"
}
```

`drop=true` means the record failed the stage-3 relevance gate (a
dedicated yes/no: would this PR's actual code change move LCP, CLS, INP,
or a closely related metric) — every other field is empty for those rows.

## Numbers

Full run over the 5-year backfilled source corpus (2021–2026):

| | |
|---|---:|
| Source records | 14,965 |
| Enriched with real title/body/comments | 14,919 (99.7%) |
| CWV-motivated (passed the relevance gate) | 4,163 (27.8%) |
| Routed to an existing playbook | 1,861 |
| Routed as novel | 2,302 |
| Raw HDBSCAN clusters | 75 |
| Confirmed coherent | 20 |
| Final novel techniques | 9 |
| Existing playbooks enriched | 17 |
| Generated playbook files | 26 |

## Collection method

1. **Source (GH Archive scan):** merged PRs matching a bot before/after-
   report template, or a non-bot human review/review-comment matching a
   broad performance vocabulary (no parsed delta for the latter — direction
   gets judged downstream from real evidence, never assumed from the
   marker match).
2. **Enrich:** backfill title/body/comments/reviews via GitHub GraphQL,
   batched via query aliases; a second paginated pass closes any gap from
   a PR that had more comments/reviews than the first pass's page cap.
3. **Extract:** a dedicated yes/no judges CWV relevance first — grounded in
   specific metrics (LCP/CLS/INP/TTFB/FCP/TBT/bundle size/request count),
   with forced reasoning before the verdict — then, only for what passes,
   a second call extracts objective technique facts.
4. **Route:** embedding similarity narrows each PR to its top-3 candidate
   existing playbooks; an LLM verifies against their full text before
   deciding existing vs. novel — never a bare threshold.
5. **Cluster:** HDBSCAN groups the novel pool, then a dedicated coherence-
   verification call reads full evidence per candidate cluster and rejects
   anything that isn't genuinely one technique before it's ever labeled.
6. **Generate:** draft → critic → grounding check → AEM-fidelity check
   (rewrites any code example that isn't genuinely native to its claimed
   AEM flavor, e.g. a carried-over React example), with diversity-weighted
   evidence selection so one repo can't dominate a technique's evidence.

## Experiment specifications

**Models** (Azure OpenAI, `openai-compatible` backend): chat completion
`gpt-5.4-mini` for every LLM stage (relevance, extraction, routing verify,
coherence, labeling, draft/critic/grounding/AEM-fidelity); text embedding
`text-embedding-3-small` for routing's pre-filter and clustering's
HDBSCAN input. Both verified as actually deployed and callable on the
Azure Foundry resource before the run — `gpt-5` (the `.env` deployment
name) and `text-embedding-ada-002` are not callable despite being listed
in the model catalog.

**Call parameters**: `temperature=0.0` for structured/JSON calls
(relevance, extraction, routing verify, coherence, labeling),
`temperature=0.2` for free-text generation calls (draft, critic,
grounding check, AEM-fidelity check). Transient network/5xx/429 errors
retry up to 4 times with exponential backoff; a real 4xx is never
retried.

**Batching**: `BATCH_SIZE=10` records/call for extraction, `VERIFY_BATCH_
SIZE=6` for routing verify, `BATCH_SIZE=40` PRs/request for GitHub
GraphQL enrichment, `CLUSTER_CALL_BATCH_SIZE=4` clusters/call for
coherence-verification and labeling (an unbatched 72-cluster call
measured ~2M characters / ~508K tokens and hit an HTTP 400).

**Routing**: embedding pre-filter narrows each PR to its top `TOP_K=3`
candidate existing playbooks by cosine similarity before an LLM verifies
against their full text.

**Clustering**: `sklearn.cluster.HDBSCAN(min_cluster_size=4,
min_samples=2)` on L2-normalized embeddings; a cluster also needs
`distinct_repo_count >= 2` to reach the coherence-verification call.

**Timeout**: 180s per LLM call.

## License

MIT for this dataset's structure/derived content. Source PR text (titles,
bodies, patches, review comments) is quoted from public GitHub repositories
under their own individual licenses; this dataset does not relicense that
content.
