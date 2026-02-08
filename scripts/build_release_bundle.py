from __future__ import annotations

import argparse
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INCLUDE = [
    "README.md",
    "LICENSE",
    "docs/METRICS.md",
    "docs/PORTFOLIO_REPORT.md",
    "docs/RELEASE_NOTES.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/GITHUB_SETUP.md",
    "docs/COLAB_RUNBOOK.md",
    "dist/release_manifest.json",
    "eval/human_eval.md",
    "eval/results/eval_report.json",
    "eval/results/conversation_eval_report.json",
    "eval/results/safety_report.json",
    "eval/results/final_audit_report.json",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics(report: dict[str, Any]) -> dict[str, Any]:
    if isinstance(report.get("metrics"), dict):
        return report["metrics"]
    if isinstance(report.get("summary"), dict):
        return report["summary"]
    return {}


def build_release_summary(
    eval_report: dict[str, Any],
    conversation_report: dict[str, Any],
    safety_report: dict[str, Any],
) -> str:
    offline = _metrics(eval_report)
    conv = _metrics(conversation_report)
    safety = _metrics(safety_report)

    lines = [
        "# Release Summary",
        "",
        "## Metrics Snapshot",
        f"- offline.decision_accuracy: {offline.get('decision_accuracy', 'N/A')}",
        f"- offline.tool_validity_rate: {offline.get('tool_validity_rate', 'N/A')}",
        f"- offline.sequence_correct_rate: {offline.get('sequence_correct_rate', 'N/A')}",
        f"- offline.efficiency_rate: {offline.get('efficiency_rate', 'N/A')}",
        f"- conversation.task_success_rate: {conv.get('task_success_rate', 'N/A')}",
        f"- conversation.avg_turns_to_resolution: {conv.get('avg_turns_to_resolution', 'N/A')}",
        f"- conversation.slot_filling_accuracy: {conv.get('slot_filling_accuracy', 'N/A')}",
        f"- conversation.evidence_handling_accuracy: {conv.get('evidence_handling_accuracy', 'N/A')}",
        f"- safety.pass_rate: {safety.get('pass_rate', 'N/A')}",
        "",
        "## Included Bundle Files",
        "- docs, key reports, and release checklist.",
        "",
        "## Notes",
        "- CUDA-required training artifacts are not bundled by default.",
        "- Attach model adapters separately in GitHub Releases if available.",
    ]
    return "\n".join(lines) + "\n"


def build_bundle(repo_root: Path, output_dir: Path, includes: list[str]) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"release_bundle_{ts}.tar.gz"

    included: list[str] = []
    missing: list[str] = []

    with tarfile.open(bundle_path, "w:gz") as tar:
        for rel in includes:
            p = repo_root / rel
            if p.exists():
                tar.add(p, arcname=rel)
                included.append(rel)
            else:
                missing.append(rel)

    return {
        "bundle_path": str(bundle_path),
        "included_files": included,
        "missing_files": missing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GitHub release bundle from current artifacts.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--release-summary", type=Path, default=Path("docs/RELEASE_SUMMARY.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()

    eval_report = load_json(repo_root / "eval/results/eval_report.json")
    conv_report = load_json(repo_root / "eval/results/conversation_eval_report.json")
    safety_report = load_json(repo_root / "eval/results/safety_report.json")

    summary_text = build_release_summary(eval_report, conv_report, safety_report)
    args.release_summary.parent.mkdir(parents=True, exist_ok=True)
    args.release_summary.write_text(summary_text, encoding="utf-8")

    includes = list(DEFAULT_INCLUDE)
    if args.release_summary.as_posix() not in includes:
        includes.append(args.release_summary.as_posix())

    bundle = build_bundle(repo_root, args.output_dir, includes)

    print(
        json.dumps(
            {
                "release_summary": str(args.release_summary),
                "bundle_path": bundle["bundle_path"],
                "included_files": len(bundle["included_files"]),
                "missing_files": len(bundle["missing_files"]),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
