from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.release_prep import metric, render_release_notes


def test_metric_prefers_metrics_then_summary():
    assert metric({"metrics": {"x": 1}}, "x") == "1"
    assert metric({"summary": {"x": 2}}, "x") == "2"
    assert metric({}, "x") == "N/A"


def test_render_release_notes_replaces_known_tokens():
    template = "decision_accuracy: <value_decision_accuracy>\npass_rate: <value_safety_pass_rate>\n"
    out = render_release_notes(
        template,
        {"metrics": {"decision_accuracy": 0.5}},
        {"summary": {"pass_rate": 0.8}},
    )
    assert "<value_decision_accuracy>" not in out
    assert "<value_safety_pass_rate>" not in out
    assert "0.5" in out
    assert "0.8" in out
