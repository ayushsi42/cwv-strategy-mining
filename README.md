# cwv-playbook-miner

Standalone pipeline that mines real, merged GitHub PRs for measured Core Web
Vitals techniques and generates platform-neutral candidates grounded in the
original PR bodies and patches.

Candidates land in `candidates/` for manual review only. The pipeline does
not translate source techniques to another CMS, framework, or delivery
platform.

See `docs/pipeline-design.md` for the full design (stage-by-stage, what's
verified against real data, known limitations).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Required: copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` --
the LLM stages (extract/classify/generate) run on the real OpenAI API
(`gpt-5.4-mini` by default; see `docs/pipeline-design.md` for why nano was
tried and dropped) and there is no fallback backend without it.

## Quickstart

```bash
scripts/run_demo.sh                                    # real ~4-day GH Archive window
scripts/run_demo.sh 2026-08-10T00:00:00 24              # override window
```

Or drive stages individually (each reads/writes JSONL under `data/processed/`,
so intermediate output is always inspectable):

```bash
cwv-playbook-miner source --start 2026-08-10T00:00:00 --hours 24
cwv-playbook-miner backfill --start 2025-08-18T00:00:00 --end 2026-08-18T00:00:00 --workers 4 --api-workers 2
cwv-playbook-miner extract --signal-type perf_improvement --batch-size 8
cwv-playbook-miner extract --signal-type perf_decrease
cwv-playbook-miner cluster
cwv-playbook-miner classify
cwv-playbook-miner antipatterns
cwv-playbook-miner generate
```

`extract` evaluates eight compact PR records per LLM call by default. It combines
page-performance rejection, structured extraction, assignment to one of 15 stable
parent strategies, and a reusable sub-strategy proposal. Results are cached by PR
content, prompt version, backend, and model, so unchanged records do not consume
another call.

`cluster` is a statistical aggregation stage rather than one-output-per-PR.
Exact sub-strategy aliases merge locally. Ambiguous sibling names are resolved in
batches and only within the same parent. A one-off child remains provisional; it is
promoted after repetition across repositories. Parent strategies organize the
registry; only coherent child strategies become playbooks. A child requires
3 observations across 2 repositories and 70% directional consistency.
Techniques outside all 15 parents enter `taxonomy_proposals.jsonl` for human review;
they never expand the parent taxonomy automatically.

Generation is two-pass: an evidence-grounded draft followed by a technical critic.
The critic-revised Markdown is written directly; the local contract remains available
for tests and diagnostics but does not block candidate output.
