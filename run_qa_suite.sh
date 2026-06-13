#!/usr/bin/env bash
#
# QA Suite Runner — one command for the whole QA system.
#
# Runs:
#   - All test_qa_buildNN.py files (1 through the highest shipped build).
#   - The scenario runner over contracts/ and journeys/.
#
# Reports:
#   - Per-test pass/fail.
#   - Final unified summary.
#   - Non-zero exit code on any failure.
#
# Output is plain text. For machine-readable, pipe individual commands
# (the suite runner exists for humans + CI bash hooks, not as a JSON
# emitter).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

pass=0
fail=0
log_dir="scenario_contracts/reports"
mkdir -p "$log_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$log_dir/suite_${ts}.log"

run_test() {
    local name="$1"
    local cmd="$2"
    echo "── $name ──"
    if eval "$cmd" >> "$log" 2>&1; then
        echo "  ✓  $name"
        pass=$((pass + 1))
    else
        echo "  ✗  $name (see $log)"
        fail=$((fail + 1))
    fi
}

run_scenario_runner() {
    # Run the scenario runner and treat output as the source of truth.
    # The runner exits 2 when invalid scenarios are present (intentional
    # QA-01 goldens always make this true for contracts/), but we only
    # care whether FAIL count is 0.
    local name="$1"
    local cmd="$2"
    echo "── $name ──"
    local out
    out="$(eval "$cmd" 2>&1)"
    echo "$out" >> "$log"
    if echo "$out" | grep -qE "FAIL: 0\b"; then
        echo "  ✓  $name"
        pass=$((pass + 1))
    else
        echo "  ✗  $name (see $log)"
        fail=$((fail + 1))
    fi
}

echo
echo "== QA Suite Runner =="
echo "Log: $log"
echo

# 1) All per-build QA regressions.
for f in test_qa_build*.py; do
    [ -f "$f" ] || continue
    run_test "$f" "python3 $f"
done

# 2) The scenario runner over the directory tree.
#
# Note: contracts/ contains 4 designed-to-fail goldens from QA-01
# (golden_db_fail, golden_ui_fail, golden_invalid_shape,
# golden_missing_metadata). Their failure / invalid outcomes are
# correct behavior — verified individually by test_qa_build01.py
# above. Running --tag release_gate scopes to the scenarios that
# SHOULD pass.
#
# journeys/ has no designed-to-fail fixtures, so we run it directly.
run_scenario_runner "release_gate scenarios" \
    "python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate"
run_scenario_runner "journeys" \
    "python3 -m scenario_contracts.lib.runner scenario_contracts/journeys/"

echo
echo "── summary ──"
echo "  PASS: $pass"
echo "  FAIL: $fail"
echo

if [ "$fail" -gt 0 ]; then
    echo "Suite failed. Inspect $log for details."
    exit 1
fi
echo "Suite green."
exit 0
