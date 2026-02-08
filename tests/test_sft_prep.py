from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.sft_train import build_sft_records, build_synthetic_example


def test_build_synthetic_example_contains_sections():
    case = {
        "case_id": "CASE-1",
        "customer_message": "My item is defective.",
        "issue_type": "defective",
        "extracted_fields": {
            "order_id": "ORD-1",
            "merchant_id": "M-1",
            "order_date": "2025-01-01",
            "delivery_date": "2025-01-05",
        },
        "tool_targets": {"get_policy": {"item_category": "electronics"}},
        "policy_decision": {
            "next_action": "request_info",
            "decision_reason": "Need photo",
            "missing_info": ["photo_proof"],
            "refund_amount": "0.00",
        },
    }
    ex = build_synthetic_example(case)
    assert ex["source"] == "synthetic_case"
    assert "<|user|>" in ex["text"]
    assert "<|assistant|>" in ex["text"]
    assert "lookup_order" in ex["text"]


def test_build_sft_records_mixes_sources():
    synthetic = [
        {
            "case_id": "CASE-1",
            "customer_message": "Late delivery",
            "issue_type": "late_delivery",
            "extracted_fields": {
                "order_id": "ORD-1",
                "merchant_id": "M-1",
                "order_date": "2025-01-01",
                "delivery_date": "2025-01-05",
            },
            "tool_targets": {"get_policy": {"item_category": "fashion"}},
            "policy_decision": {
                "next_action": "deny",
                "decision_reason": "Outside window",
                "missing_info": [],
                "refund_amount": "0.00",
            },
        }
    ]
    tweetsumm = [{"dialog": "customer asked", "summary": "agent asked for order id"}]
    conversation = [{"source": "conversation_synthetic", "text": "<|user|>x<|assistant|>y"}]
    rows = build_sft_records(
        synthetic,
        tweetsumm,
        conversation,
        max_synthetic=1,
        max_tweetsumm=1,
        max_conversation=1,
    )
    assert len(rows) == 3
    sources = sorted(r["source"] for r in rows)
    assert sources == ["conversation_synthetic", "synthetic_case", "tweetsumm"]
