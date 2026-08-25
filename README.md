# cwv-playbook-miner

A pipeline that mines real, merged GitHub PRs for measured Core Web Vitals (CWV)
techniques and turns them into platform-neutral, evidence-grounded playbook
candidates — each one traceable back to the specific PRs that support it.

Candidates land in [`candidates/`](candidates/) for manual review. The pipeline
does not translate a technique into another CMS, framework, or delivery
platform; it only decides *whether a reusable technique is real* and *what
evidence backs it*.

The mined dataset (raw source records, extracted patterns, and the final
candidates) is published at
**[Ayush-Singh/cwv-strategy-mining-dataset](https://huggingface.co/datasets/Ayush-Singh/cwv-strategy-mining-dataset)**.

## Why this exists

Automated Lighthouse/bundle-size bots (`treosh`, `relative-ci`, `calibre`,
`webpagetest`, ...) are the obvious place to find measured before/after
performance data on a PR, but they're a small fraction of real,
performance-motivated PRs — most authors and reviewers never run one. This
project's sourcing stage was built and then rebuilt around that observation:
start from the narrow, precisely-measured bot signal, then widen discovery to
the much larger pool of PRs where a human reviewer or another automated tool
mentions performance in plain text, without requiring a parsed before/after
number for every PR to be worth mining.

## Pipeline

```text
source (stage 0) -> extract (stage 2) -> cluster (stage 3)
                  -> classify (stage 4) -> match regressions (stage 5)
                  -> generate (stage 6)
```

### Stage 0 — source

Scans [GH Archive](https://www.gharchive.org/)'s public event stream, hour by
hour, for merged PRs with one of **four free signals**, each intersected with
a `PullRequestEvent` merge event for the same PR:

| # | Event type | Actor | Marker set | Produces |
|---|---|---|---|---|
| 1 | `IssueCommentEvent` | bot (`[bot]` suffix) | narrow, structured (`BOT_COMMENT_MARKERS`) | a Tier-A candidate once its comment(s) parse a real before/after number via a known bot-report template (`labeling/registry.py`) |
| 2 | `PullRequestReviewEvent` / `PullRequestReviewCommentEvent` | bot | same narrow marker set | same Tier-A path — some CI perf bots post via the Review API instead of a plain comment |
| 3 | `PullRequestReviewEvent` / `PullRequestReviewCommentEvent` | **non-bot** (human) | broad, human-language (`HUMAN_PERF_MARKERS`: LCP/CLS/INP, "bundle size", "lazy load", "code split", "reduce render", ...) | a `perf_flagged` candidate — no parsed delta, but a real repo+PR pointer and the flagging comment's text |
| 4 | `PullRequestEvent` | — | `action == "merged"` | the merge-confirmation signal all three above intersect against |

GitHub strips PR `title`/`body` from `PullRequestEvent` itself (confirmed
against both raw archive files and BigQuery/ClickHouse's own mirror of the
same data — full pre-2024, 100% empty since), so no free channel can
keyword-search a PR's *own* text. Channels 1–3 work around that by matching
against comment/review *bodies*, which still carry the PR number in their
payload.

Two known-bot-actor pitfalls, fixed after being caught on real data:
- Some automated review tools (CodeRabbit, Copilot's PR reviewer, etc.) don't
  use the `[bot]`-suffix convention (`Copilot`'s login is bare) — `is_bot_actor`
  has an explicit allowlist for these on top of the suffix check.
- A bot's multi-thousand-character auto-review dump can coincidentally contain
  a narrow marker substring (e.g. "bundle size" mentioned in passing) even on
  an unrelated PR. `human_flagged_candidates` explicitly excludes bot actors
  regardless of which marker set technically matched, and
  `human_comment_matches_markers` rejects bodies over ~1500 characters as a
  backstop against future unknown tools.

Downloading and pre-filtering is `ProcessPoolExecutor`-parallel (the
decompress+JSON-parse step is CPU-bound, so threads gave zero speedup under
the GIL — measured live, 4 vs 32 threads both ~1.2 hours/sec; processes hit
~8.2 hours/sec, a full year in ~20 minutes of scan time instead of ~2 hours).
`backfill` runs this in resumable, checkpointed 24-hour chunks so a multi-day
sweep survives interruption or a GitHub API rate limit.

### Stage 2 — extract

One LLM call evaluates a batch of PRs (8 by default) and returns, per PR:
whether it's a genuine page-performance change, its parent strategy (one of
15 stable categories), a proposed reusable sub-strategy, mechanism, affected
resource, render phase, and — for `perf_flagged` records specifically, which
never had a bot-parsed delta — an `inferred_signal_type`
(`perf_improvement`/`perf_decrease`), the model's own judgment of direction
from the diff and the flagging comment. A `perf_flagged` record the model
can't confidently direction-classify is dropped, never guessed at, since
downstream aggregation trusts a pattern's polarity verbatim.

Extraction is cached per PR content + prompt version + backend + model, so
reruns after a prompt or taxonomy change only touch what's actually new.

### Stage 3 — cluster

Statistical aggregation, not LLM judgment. Exact sub-strategy names merge
locally; ambiguous sibling names are resolved in batches, scoped to the same
parent only. A technique needs **≥2 observations, ≥2 distinct repositories,
and ≥70% directional consistency** by default to become an eligible
candidate; anything short of that stays provisional. Techniques that don't
fit any of the 15 parents go to a human-review proposal pool rather than
silently expanding the taxonomy.

### Stage 4 — classify

An LLM pass judges each statistically-eligible cluster for generic CWV
usefulness and risk tier — raw PR content isn't resent here, only the
aggregated cluster summary.

### Stage 5 — match regressions

Cross-references each surviving cluster's applicable signals against
extracted `perf_decrease` patterns, surfacing real anti-pattern evidence
(what *not* to do) alongside the positive technique.

### Stage 6 — generate

Two-pass generation: an evidence-grounded draft from the cluster's real
source PRs, then a technical-critic pass that rewrites for correctness and
platform-neutrality. The critic's output is written directly.

Every stage reads/writes JSONL under `data/processed/`, so any intermediate
result is inspectable (`jq . data/processed/clusters.jsonl`) or independently
rerunnable.

## Results (full year, 2025-08-18 → 2026-08-18)

| | |
|---|---:|
| Hours scanned | 8,760 (full year) |
| Distinct repositories touched | 1,054 |
| Raw source records | 1,750 |
| — bot-parsed `perf_improvement` | 202 |
| — bot-parsed `perf_decrease` | 334 |
| — non-bot `perf_flagged` | **1,214** |
| Valid extracted patterns | 454 |
| — from `perf_flagged` | **361 (80%)** |
| Canonical techniques (post-clustering) | 218 |
| Techniques meeting the evidence bar | **29** |
| Candidate playbooks generated | 29 |

The non-bot discovery channel added in this project's second phase isn't a
minor supplement — **80% of everything that survived extraction came from
it**, and the flagship result (below) exists almost entirely because of it.

### Top techniques by evidence strength

| Technique | Parent | Observations | Repos | Consistency |
|---|---|---:|---:|---:|
| lazy-load optional feature code behind dynamic import | javascript-delivery | 53 | 47 | 91% |
| remove unused code from the shipped entry bundle | network-payload | 19 | 18 | 89% |
| remove unused dependency from shipped bundle | network-payload | 18 | 16 | 83% |
| module import tree-shaking | javascript-delivery | 8 | 8 | 100% |
| reduce unnecessary wrapper nodes in component composition | dom-complexity | 7 | 7 | 71% |
| reserve space only when async content will actually appear | layout-stability | 7 | 6 | 86% |

### Candidates by parent strategy

| Parent strategy | Candidates |
|---|---:|
| network-payload | 8 |
| javascript-delivery | 7 |
| image-delivery | 3 |
| layout-stability | 2 |
| font-delivery | 2 |
| dom-complexity | 2 |
| third-party-cost | 1 |
| server-response | 1 |
| resource-prioritization | 1 |
| main-thread-computation | 1 |
| cache-and-data-reuse | 1 |

Full parent taxonomy (`src/cwv_playbook_miner/taxonomy.py`): JavaScript
delivery, main-thread computation, interaction responsiveness, rendering and
hydration, layout stability, image delivery, font delivery, CSS delivery,
critical-resource prioritization, network payload reduction, cache and data
reuse, server response latency, third-party cost, DOM and rendering
complexity, media and embedded content.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` (default backend)
or `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_NAME` for an OpenAI-compatible
endpoint (Azure OpenAI, vLLM, etc. — pass `--backend openai-compatible`). The
LLM stages (extract/classify/generate) have no fallback without one of these.

## Usage

```bash
# One window
cwv-playbook-miner source --start 2026-08-10T00:00:00 --hours 24 --workers 16

# Resumable, checkpointed historical sweep
cwv-playbook-miner backfill --start 2025-08-18T00:00:00 --end 2026-08-18T00:00:00 \
  --chunk-hours 24 --workers 16 --api-workers 4

# Downstream stages
cwv-playbook-miner extract --signal-type perf_improvement
cwv-playbook-miner extract --signal-type perf_decrease
cwv-playbook-miner extract --signal-type perf_flagged
cwv-playbook-miner cluster
cwv-playbook-miner classify
cwv-playbook-miner antipatterns
cwv-playbook-miner generate

# Or chain everything for one window
cwv-playbook-miner run-all --start 2026-08-10T00:00:00 --hours 24
```

`--workers` controls the source-stage `ProcessPoolExecutor` size — match it
to available cores. `--api-workers` bounds concurrent `gh api` calls (merge
confirmation, comment history, diff fetch), which are the only non-free calls
in the whole pipeline and the only ones subject to GitHub's rate limit.

## Testing

```bash
.venv/bin/pytest -q
```

32 tests cover: sequential-vs-process-pool scan equivalence, all four
sourcing channels (bot-template match via comment/review/review-comment, and
human-marker match via review/review-comment, including the bot-actor and
long-body false-positive regressions caught on real data), statistical
aggregation (including a `perf_flagged`-origin pattern with no metric), and
the extraction contract (`inferred_signal_type` resolution and drop-on-
ambiguous behavior).

## Repo layout

```text
src/cwv_playbook_miner/
  sourcing/       stage 0 -- GH Archive scan, gh api calls
  labeling/       stage 1 -- bot-report template registry, structural fingerprinting
  extraction/     stage 2 -- LLM pattern extraction, PR record shape
  aggregation/    stage 3 -- statistical clustering, taxonomy registry
  classification/ stage 4 -- generic usefulness/risk judgment
  antipatterns/   stage 5 -- regression cross-reference
  generation/     stage 6 -- draft + technical-critic candidate rendering
  taxonomy.py     the 15 stable parent strategies
data/processed/  every stage's JSONL output (gitignored)
candidates/      final generated playbook candidates
docs/pipeline-design.md  deeper design notes, candidate file contract
```

See [`docs/pipeline-design.md`](docs/pipeline-design.md) for the candidate
file contract and current known limitations.
