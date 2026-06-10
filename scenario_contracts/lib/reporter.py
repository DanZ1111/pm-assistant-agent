"""Markdown + JSON report writer.

Each run emits two files into scenario_contracts/reports/:
  run_<timestamp>.md   — human-readable summary
  run_<timestamp>.json — machine-readable for CI / aggregation

reports/ is gitignored.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def write_report(results):
    """Write markdown + JSON report; return (md_path, json_path)."""
    _ensure_reports_dir()
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    md_path = REPORTS_DIR / f"run_{ts}.md"
    json_path = REPORTS_DIR / f"run_{ts}.json"

    md_path.write_text(_render_markdown(results, ts), encoding="utf-8")
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return md_path, json_path


def _render_markdown(results, ts):
    pass_count = sum(1 for r in results if r["outcome"] == "pass")
    fail_count = sum(1 for r in results if r["outcome"] == "fail")
    invalid_count = sum(1 for r in results if r["outcome"] == "invalid")
    skip_count = sum(1 for r in results if r["outcome"] == "skip")

    lines = [
        f"# Scenario Contract Run — {ts}",
        "",
        f"PASS: {pass_count} | FAIL: {fail_count} | INVALID: {invalid_count} | SKIP: {skip_count}",
        "",
        "| Outcome | ID | Title | Detail |",
        "|---|---|---|---|",
    ]
    for r in results:
        detail = r.get("detail", "") or ""
        detail = detail.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['outcome'].upper()} | `{r.get('id', '?')}` | "
            f"{r.get('title', '?')} | {detail} |"
        )
    lines.append("")
    return "\n".join(lines)
