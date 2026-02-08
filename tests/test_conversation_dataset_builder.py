from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipelines.build_conversation_dataset import build_records, build_snapshots, normalize_reason


def _sample_case(issue_type: str = "damaged") -> dict:
    return {
        "case_id": "CASE-1",
        "customer_message": "I want a refund",
        "issue_type": issue_type,
        "extracted_fields": {
            "order_id": "ORD-1",
            "item_id": "ITEM-1",
            "customer_id": "C-1",
        },
        "policy_decision": {
            "next_action": "approve_return_and_refund",
            "refund_amount": "12.50",
            "decision_reason": "Eligible",
        },
    }


def test_normalize_reason_mapping():
    assert normalize_reason("refund_request") == "changed_mind"
    assert normalize_reason("missing_item") == "wrong_item"
    assert normalize_reason("damaged") == "damaged"


def test_build_snapshots_for_damaged_includes_evidence_stage():
    snaps = build_snapshots(_sample_case("damaged"))
    stages = [s["stage"] for s in snaps]
    assert "need_identifier" in stages
    assert "need_reason" in stages
    assert "need_evidence" in stages
    assert "terminal" in stages


def test_build_records_shapes():
    sft_rows, dpo_rows = build_records([_sample_case("changed_mind")])
    assert len(sft_rows) >= 3
    assert len(dpo_rows) >= 3
    assert "text" in sft_rows[0]
    assert "prompt" in dpo_rows[0]
    assert "chosen" in dpo_rows[0]
    assert "rejected" in dpo_rows[0]
