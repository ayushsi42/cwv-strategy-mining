#!/usr/bin/env bash
# Small, real end-to-end demo: scans a modest GH Archive window, labels and
# extracts measured observations, statistically aggregates recurring techniques,
# and generates platform-neutral candidates that pass the evidence thresholds.
#
# Usage: scripts/run_demo.sh [START_ISO] [HOURS]
#   scripts/run_demo.sh 2026-08-10T00:00:00 96

set -euo pipefail
cd "$(dirname "$0")/.."

START="${1:-2026-08-10T00:00:00}"
HOURS="${2:-96}"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e .

echo "=== cwv-playbook-miner demo run: ${START} + ${HOURS}h ==="
python -m cwv_playbook_miner.cli run-all --start "$START" --hours "$HOURS"

echo
echo "=== candidates/ ==="
ls -la candidates/ 2>/dev/null || echo "(no candidates written -- see stage output above for why)"
