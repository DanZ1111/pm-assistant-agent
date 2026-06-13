#!/usr/bin/env bash
#
# QA Loop Runner — measure flakiness over N runs of the suite.
#
# Usage:
#   bash run_qa_loop.sh 10
#
# Runs `bash run_qa_suite.sh` N times back-to-back. After each run,
# records each test's pass/fail. After all runs, reports:
#   - How many runs were green / red overall.
#   - Per-test flakiness (test that PASSED in some runs and FAILED in
#     others — the load-bearing signal).
#
# Output:
#   - stdout: per-run + final flakiness report.
#   - scenario_contracts/reports/loop_<ts>.json: machine-readable.
#
# This is the basis for the stable-credibility promotion rule (see
# STABLE_CREDIBILITY.md): a scenario earns the `MATURITY="stable"`
# label after 10 consecutive green runs here.
#
# Pure POSIX-ish shell (no bash 4 features) so it runs on the default
# macOS /bin/bash.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

N="${1:-10}"
if ! [[ "$N" =~ ^[0-9]+$ ]] || [ "$N" -lt 1 ]; then
    echo "usage: bash run_qa_loop.sh N (positive integer)" >&2
    exit 2
fi

report_dir="scenario_contracts/reports"
mkdir -p "$report_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
json_path="$report_dir/loop_${ts}.json"
tmp_dir="$(mktemp -d)"

# We track pass/fail per-test in files under $tmp_dir/by_test/<sanitized-name>.
# Each line is "PASS" or "FAIL", one per run.
mkdir -p "$tmp_dir/by_test"

echo "== QA Loop Runner — $N runs =="
echo "Report: $json_path"
echo

green_runs=0
red_runs=0
for i in $(seq 1 "$N"); do
    run_log="$tmp_dir/run_${i}.log"
    if bash run_qa_suite.sh > "$run_log" 2>&1; then
        green_runs=$((green_runs + 1))
        printf "  run %2d/%-2d  ✓\n" "$i" "$N"
    else
        red_runs=$((red_runs + 1))
        printf "  run %2d/%-2d  ✗\n" "$i" "$N"
    fi

    # Per-test extraction. Suite output lines look like:
    #   "  ✓  test_qa_build03.py"
    #   "  ✗  release_gate scenarios (see ...)"
    while IFS= read -r line; do
        outcome=""
        name=""
        case "$line" in
            "  ✓  "*)
                outcome="PASS"
                name="${line#  ✓  }"
                name="${name%% (*}"
                ;;
            "  ✗  "*)
                outcome="FAIL"
                name="${line#  ✗  }"
                name="${name%% (*}"
                ;;
        esac
        if [ -n "$name" ]; then
            safe="$(printf '%s' "$name" | tr -c 'A-Za-z0-9._-' '_')"
            printf "%s\n" "$outcome" >> "$tmp_dir/by_test/$safe"
            # Also record the human-readable name in a parallel file.
            printf "%s\n" "$name" > "$tmp_dir/by_test/${safe}.name"
        fi
    done < "$run_log"
done

# Flakiness pass.
echo
echo "── per-test flakiness ──"
flaky=0
test_count=0
{
    for outcome_file in "$tmp_dir"/by_test/*; do
        case "$outcome_file" in
            *.name) continue;;
        esac
        [ -f "$outcome_file" ] || continue
        test_count=$((test_count + 1))
        # awk normalizes counts to clean integers (grep -c emits trailing
        # whitespace on some platforms which breaks arithmetic).
        p=$(awk '/^PASS$/ {n++} END {print n+0}' "$outcome_file")
        f=$(awk '/^FAIL$/ {n++} END {print n+0}' "$outcome_file")
        name_file="${outcome_file}.name"
        if [ -f "$name_file" ]; then
            name="$(cat "$name_file")"
        else
            name="$(basename "$outcome_file")"
        fi
        if [ "$f" -gt 0 ] && [ "$p" -gt 0 ]; then
            printf "  FLAKY  %s   PASS:%d  FAIL:%d\n" "$name" "$p" "$f"
            flaky=$((flaky + 1))
        fi
        printf '%s\t%d\t%d\n' "$name" "$p" "$f" >> "$tmp_dir/per_test.tsv"
    done
}
if [ "$flaky" -eq 0 ]; then
    echo "  No flaky scenarios across $N runs."
fi

# Build JSON report from per_test.tsv.
{
    printf '{\n'
    printf '  "ts": "%s",\n' "$ts"
    printf '  "n_runs": %d,\n' "$N"
    printf '  "green_runs": %d,\n' "$green_runs"
    printf '  "red_runs": %d,\n' "$red_runs"
    printf '  "flaky": %d,\n' "$flaky"
    printf '  "tests": {\n'
    first=1
    if [ -f "$tmp_dir/per_test.tsv" ]; then
        while IFS=$'\t' read -r name p f; do
            if [ "$first" -eq 1 ]; then first=0; else printf ',\n'; fi
            printf '    "%s": {"pass": %s, "fail": %s}' "$name" "$p" "$f"
        done < "$tmp_dir/per_test.tsv"
    fi
    printf '\n  }\n'
    printf '}\n'
} > "$json_path"

rm -rf "$tmp_dir"

echo
echo "── summary ──"
echo "  Green runs: $green_runs / $N"
echo "  Red runs:   $red_runs"
echo "  Flaky:      $flaky"
echo "  Report:     $json_path"
echo

if [ "$red_runs" -gt 0 ] || [ "$flaky" -gt 0 ]; then
    exit 1
fi
exit 0
