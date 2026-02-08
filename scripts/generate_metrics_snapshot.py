from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _get_metrics(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("metrics")
    if isinstance(value, dict):
        return value
    value = report.get("summary")
    if isinstance(value, dict):
        return value
    return {}


def render_markdown(
    eval_report: dict[str, Any],
    conversation_report: dict[str, Any],
    safety_report: dict[str, Any],
    audit_report: dict[str, Any],
) -> str:
    offline = _get_metrics(eval_report)
    conversation = _get_metrics(conversation_report)
    safety = _get_metrics(safety_report)

    lines = [
        "# Current Metrics",
        "",
        "Snapshot from local evaluation artifacts.",
        "",
        "## Offline Eval (synthetic held-out)",
        f"- n: {offline.get('n', 'N/A')}",
        f"- decision_accuracy: {offline.get('decision_accuracy', 'N/A')}",
        f"- tool_validity_rate: {offline.get('tool_validity_rate', 'N/A')}",
        f"- sequence_correct_rate: {offline.get('sequence_correct_rate', 'N/A')}",
        f"- efficiency_rate: {offline.get('efficiency_rate', 'N/A')}",
        f"- avg_calls_per_episode: {offline.get('avg_calls_per_episode', 'N/A')}",
        "",
        "## Conversational Eval",
        f"- n: {conversation.get('n', 'N/A')}",
        f"- task_success_rate: {conversation.get('task_success_rate', 'N/A')}",
        f"- avg_turns_to_resolution: {conversation.get('avg_turns_to_resolution', 'N/A')}",
        f"- slot_filling_accuracy: {conversation.get('slot_filling_accuracy', 'N/A')}",
        f"- evidence_handling_accuracy: {conversation.get('evidence_handling_accuracy', 'N/A')}",
        f"- terminal_state_rate: {conversation.get('terminal_state_rate', 'N/A')}",
        "",
        "## Safety Suite",
        f"- total: {safety.get('total', 'N/A')}",
        f"- passed: {safety.get('passed', 'N/A')}",
        f"- pass_rate: {safety.get('pass_rate', 'N/A')}",
        "",
        "## Final Audit",
        f"- ok: {audit_report.get('ok', 'N/A')}",
        f"- warnings: {len(audit_report.get('warnings', [])) if isinstance(audit_report.get('warnings'), list) else 'N/A'}",
        "",
        "## Notes",
        "- Refresh this file after rerunning eval suites and final audit.",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate docs/METRICS.md from eval artifacts.")
    parser.add_argument(
        "--eval-report",
        type=Path,
        default=Path("eval/results/eval_report.json"),
    )
    parser.add_argument(
        "--conversation-report",
        type=Path,
        default=Path("eval/results/conversation_eval_report.json"),
    )
    parser.add_argument(
        "--safety-report",
        type=Path,
        default=Path("eval/results/safety_report.json"),
    )
    parser.add_argument(
        "--audit-report",
        type=Path,
        default=Path("eval/results/final_audit_report.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("docs/METRICS.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    md = render_markdown(
        load_json(args.eval_report),
        load_json(args.conversation_report),
        load_json(args.safety_report),
        load_json(args.audit_report),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(json.dumps({"output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
