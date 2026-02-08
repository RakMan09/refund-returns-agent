from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def metric(report: dict, key: str, default: str = "N/A") -> str:
    metrics = report.get("metrics")
    if isinstance(metrics, dict) and key in metrics:
        return str(metrics[key])
    summary = report.get("summary")
    if isinstance(summary, dict) and key in summary:
        return str(summary[key])
    return default


def render_release_notes(template: str, eval_report: dict, safety_report: dict) -> str:
    mapping = {
        "<value_decision_accuracy>": metric(eval_report, "decision_accuracy"),
        "<value_tool_validity_rate>": metric(eval_report, "tool_validity_rate"),
        "<value_sequence_correct_rate>": metric(eval_report, "sequence_correct_rate"),
        "<value_efficiency_rate>": metric(eval_report, "efficiency_rate"),
        "<value_safety_pass_rate>": metric(safety_report, "pass_rate"),
    }
    out = template
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare release assets and notes in one command.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-notes", type=Path, default=Path("docs/RELEASE_NOTES.md"))
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--run-demo", action="store_true")
    parser.add_argument("--agent-url", default="http://localhost:8002")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()

    if not args.skip_audit:
        run(["python3", "scripts/final_audit.py", "--output", "eval/results/final_audit_report.json"])

    if args.run_demo:
        run(
            [
                "python3",
                "scripts/demo_scenarios.py",
                "--agent-url",
                args.agent_url,
                "--output",
                "eval/results/demo_scenarios.json",
            ]
        )

    run(
        [
            "python3",
            "scripts/generate_metrics_snapshot.py",
            "--eval-report",
            "eval/results/eval_report.json",
            "--conversation-report",
            "eval/results/conversation_eval_report.json",
            "--safety-report",
            "eval/results/safety_report.json",
            "--audit-report",
            "eval/results/final_audit_report.json",
            "--output",
            "docs/METRICS.md",
        ]
    )
    run(["python3", "scripts/generate_portfolio_report.py", "--output", "docs/PORTFOLIO_REPORT.md"])

    template_path = root / "docs/RELEASE_NOTES_TEMPLATE.md"
    template = template_path.read_text(encoding="utf-8")
    eval_report = load_json(root / "eval/results/eval_report.json")
    safety_report = load_json(root / "eval/results/safety_report.json")
    filled = render_release_notes(template, eval_report, safety_report)

    # Replace simple placeholders while preserving template structure.
    filled = filled.replace("decision_accuracy: <value>", f"decision_accuracy: {metric(eval_report, 'decision_accuracy')}")
    filled = filled.replace("tool_validity_rate: <value>", f"tool_validity_rate: {metric(eval_report, 'tool_validity_rate')}")
    filled = filled.replace(
        "sequence_correct_rate: <value>",
        f"sequence_correct_rate: {metric(eval_report, 'sequence_correct_rate')}",
    )
    filled = filled.replace("efficiency_rate: <value>", f"efficiency_rate: {metric(eval_report, 'efficiency_rate')}")
    filled = filled.replace("pass_rate: <value>", f"pass_rate: {metric(safety_report, 'pass_rate')}")

    args.output_notes.parent.mkdir(parents=True, exist_ok=True)
    args.output_notes.write_text(filled, encoding="utf-8")
    run(["python3", "scripts/generate_manifest.py", "--repo-root", ".", "--output", "dist/release_manifest.json"])
    run(
        [
            "python3",
            "scripts/build_release_bundle.py",
            "--repo-root",
            ".",
            "--output-dir",
            "dist",
            "--release-summary",
            "docs/RELEASE_SUMMARY.md",
        ]
    )
    print(json.dumps({"release_notes": str(args.output_notes), "bundle_dir": "dist"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
