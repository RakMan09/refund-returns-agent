from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_report(
    eval_report: dict[str, Any],
    conv_report: dict[str, Any],
    safety_report: dict[str, Any],
    audit_report: dict[str, Any],
) -> str:
    offline = eval_report.get("metrics", {})
    conv = conv_report.get("metrics", {})
    safety = safety_report.get("summary", {})
    audit_ok = audit_report.get("ok", False)

    lines = [
        "# Portfolio Report: Refund/Returns Agent",
        "",
        "## Product Overview",
        "- Stateful multi-turn customer-support chatbot for refund/return/replacement/cancellation flows.",
        "- Guided UI controls: dropdowns, multiselects, buttons, file upload, and timeline panel.",
        "- Policy-authoritative backend with strict tool schemas and guardrails.",
        "",
        "## Engineering Scope Implemented",
        "- FastAPI tool server + agent server",
        "- Postgres-backed sessions, chat messages, tool traces, and evidence records",
        "- Streamlit conversational UI with test-order creation",
        "- Deterministic policy engine and idempotent write tools",
        "- Evaluation suites (offline, conversational, safety) + human rubric",
        "- Training data pipelines for SFT and DPO (including conversation states)",
        "- CI lint/tests + docker smoke checks + release automation",
        "",
        "## Metrics Snapshot",
        f"- Offline decision_accuracy: {offline.get('decision_accuracy', 'N/A')}",
        f"- Offline tool_validity_rate: {offline.get('tool_validity_rate', 'N/A')}",
        f"- Offline efficiency_rate: {offline.get('efficiency_rate', 'N/A')}",
        f"- Conversational task_success_rate: {conv.get('task_success_rate', 'N/A')}",
        f"- Conversational avg_turns_to_resolution: {conv.get('avg_turns_to_resolution', 'N/A')}",
        f"- Safety pass_rate: {safety.get('pass_rate', 'N/A')}",
        "",
        "## Operational Validation",
        f"- Final audit passed: {audit_ok}",
        "- Demo scenarios generated: `eval/results/demo_scenarios.json`",
        "- Release bundle automation available: `scripts/release_prep.py`",
        "",
        "## Key Artifacts",
        "- `docs/METRICS.md`",
        "- `docs/RELEASE_SUMMARY.md`",
        "- `docs/RELEASE_NOTES.md`",
        "- `eval/results/eval_report.json`",
        "- `eval/results/conversation_eval_report.json`",
        "- `eval/results/safety_report.json`",
        "- `eval/results/final_audit_report.json`",
        "",
        "## Repro Commands",
        "```bash",
        "ruff check .",
        "pytest -q",
        "python3 scripts/release_prep.py --repo-root . --output-notes docs/RELEASE_NOTES.md",
        "python3 scripts/demo_scenarios.py --agent-url http://localhost:8002 --output eval/results/demo_scenarios.json",
        "```",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a portfolio-ready project report.")
    parser.add_argument("--eval-report", type=Path, default=Path("eval/results/eval_report.json"))
    parser.add_argument(
        "--conversation-report",
        type=Path,
        default=Path("eval/results/conversation_eval_report.json"),
    )
    parser.add_argument("--safety-report", type=Path, default=Path("eval/results/safety_report.json"))
    parser.add_argument("--audit-report", type=Path, default=Path("eval/results/final_audit_report.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/PORTFOLIO_REPORT.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    content = render_report(
        load_json(args.eval_report),
        load_json(args.conversation_report),
        load_json(args.safety_report),
        load_json(args.audit_report),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(json.dumps({"output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
