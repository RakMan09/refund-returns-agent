from pathlib import Path
import sys
import types

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.modules.setdefault("httpx", types.SimpleNamespace(Client=None))

from eval.conversation_eval import aggregate_results, extract_control_value, is_terminal_status


def test_terminal_status():
    assert is_terminal_status("Resolved")
    assert is_terminal_status("Refund Pending")
    assert not is_terminal_status("Awaiting Evidence")


def test_extract_control_value_first():
    controls = [
        {
            "field": "selected_order_id",
            "options": [{"label": "ORD-1", "value": "ORD-1"}],
        }
    ]
    assert extract_control_value(controls, "selected_order_id", "first") == "ORD-1"


def test_aggregate_results():
    rows = [
        {
            "task_success": True,
            "turns_to_resolution": 4,
            "slot_fill_ok": True,
            "evidence_required": True,
            "evidence_ok": True,
            "terminal_state_reached": True,
        },
        {
            "task_success": False,
            "turns_to_resolution": 6,
            "slot_fill_ok": False,
            "evidence_required": False,
            "evidence_ok": True,
            "terminal_state_reached": True,
        },
    ]
    metrics = aggregate_results(rows)
    assert metrics["n"] == 2
    assert metrics["task_success_rate"] == 0.5
    assert metrics["avg_turns_to_resolution"] == 5
    assert metrics["slot_filling_accuracy"] == 0.5
    assert metrics["evidence_handling_accuracy"] == 1.0
