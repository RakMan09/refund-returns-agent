from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FILES = [
    "docs/METRICS.md",
    "docs/PORTFOLIO_REPORT.md",
    "docs/RELEASE_SUMMARY.md",
    "docs/RELEASE_NOTES.md",
    "eval/results/eval_report.json",
    "eval/results/conversation_eval_report.json",
    "eval/results/safety_report.json",
    "eval/results/final_audit_report.json",
    "eval/results/demo_scenarios.json",
    "dist/release_manifest.json",
]


def _hours_old(path: Path) -> float:
    now = datetime.now(timezone.utc).timestamp()
    return max(0.0, (now - path.stat().st_mtime) / 3600.0)


def check(repo_root: Path, max_age_hours: float) -> dict:
    missing: list[str] = []
    stale: list[dict[str, float]] = []
    present: list[str] = []

    for rel in REQUIRED_FILES:
        p = repo_root / rel
        if not p.exists():
            missing.append(rel)
            continue
        present.append(rel)
        age = _hours_old(p)
        if age > max_age_hours:
            stale.append({"path": rel, "hours_old": round(age, 2)})

    ok = not missing and not stale
    return {
        "ok": ok,
        "required_count": len(REQUIRED_FILES),
        "present_count": len(present),
        "missing": missing,
        "stale": stale,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ship-ready gate for final release.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--max-age-hours", type=float, default=168.0)
    parser.add_argument("--output", type=Path, default=Path("eval/results/ship_ready_gate.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = check(args.repo_root.resolve(), args.max_age_hours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "output": str(args.output)}, ensure_ascii=True))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
