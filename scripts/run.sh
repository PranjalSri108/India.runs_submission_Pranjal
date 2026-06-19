#!/usr/bin/env bash
# run.sh — end-to-end Redrob Ranker run with wall-clock + peak-RAM reporting.
#
# Phase 6 checkpoint: must finish in < 5 min and stay < 16 GB on a CPU box.
# Produces submission.csv, then runs the format validator.
set -euo pipefail

cd "$(dirname "$0")/.."

PYBIN=".venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="python3"
# Clear PYTHONPATH so a system/ROS site-packages doesn't shadow our imports.
export PYTHONPATH=

TIMEFILE="$(mktemp)"
trap 'rm -f "$TIMEFILE"' EXIT

echo "=== Redrob Ranker — end-to-end run ==="
echo "python: $PYBIN"
echo

# -v gives "Elapsed (wall clock)" and "Maximum resident set size" (peak RAM).
/usr/bin/time -v "$PYBIN" -m src.rank 2> "$TIMEFILE"

echo
echo "=== resource usage ==="
grep -E "Elapsed \(wall clock\)|Maximum resident set size" "$TIMEFILE" | sed 's/^[[:space:]]*//'
PEAK_KB=$(grep "Maximum resident set size" "$TIMEFILE" | grep -oE "[0-9]+$")
PEAK_GB=$(awk "BEGIN{printf \"%.2f\", $PEAK_KB/1024/1024}")
echo "peak RAM: ${PEAK_GB} GB  (budget: 16 GB)"

echo
echo "=== validating submission.csv ==="
"$PYBIN" validate_submission.py submission.csv
