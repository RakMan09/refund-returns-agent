from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_portfolio_report import render_report


def test_render_report_contains_core_sections():
    text = render_report(
        {"metrics": {"decision_accuracy": 0.2, "tool_validity_rate": 1.0, "efficiency_rate": 0.9}},
        {"metrics": {"task_success_rate": 1.0, "avg_turns_to_resolution": 5}},
        {"summary": {"pass_rate": 0.8}},
        {"ok": True},
    )
    assert "## Product Overview" in text
    assert "## Engineering Scope Implemented" in text
    assert "Offline decision_accuracy: 0.2" in text
    assert "Safety pass_rate: 0.8" in text
