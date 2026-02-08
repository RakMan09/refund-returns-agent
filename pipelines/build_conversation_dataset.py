from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True)


def normalize_reason(issue_type: str) -> str:
    if issue_type in {"refund_request", "return_request"}:
        return "changed_mind"
    if issue_type == "missing_item":
        return "wrong_item"
    return issue_type


def terminal_status(next_action: str) -> str:
    if next_action in {"approve_refund", "approve_return_and_refund"}:
        return "Refund Pending"
    if next_action == "deny":
        return "Denied"
    if next_action == "escalate":
        return "Escalated"
    return "Awaiting User Info"


def snapshot_need_identifier(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_state": {"customer_identifier": None, "selected_order_id": None, "selected_items": [], "reason": None},
        "assistant_target": {
            "assistant_message": "Please share order ID, email, or phone last 4 so I can find your orders.",
            "status_chip": "Awaiting User Info",
            "next_controls": [
                {"control_type": "text", "field": "identifier", "label": "Order ID / email / phone last 4"}
            ],
            "tool_intent": [],
        },
        "stage": "need_identifier",
        "history": [case.get("customer_message", "")],
    }


def snapshot_need_reason(case: dict[str, Any]) -> dict[str, Any]:
    ex = case.get("extracted_fields", {})
    order_id = ex.get("order_id")
    item_id = ex.get("item_id")
    return {
        "slot_state": {
            "customer_identifier": ex.get("customer_id", "known_customer"),
            "selected_order_id": order_id,
            "selected_items": [item_id] if item_id else [],
            "reason": None,
        },
        "assistant_target": {
            "assistant_message": "Select the reason for your request.",
            "status_chip": "Awaiting User Choice",
            "next_controls": [
                {
                    "control_type": "buttons",
                    "field": "reason",
                    "label": "Reason",
                    "options": [
                        {"label": "Damaged", "value": "damaged"},
                        {"label": "Wrong Item", "value": "wrong_item"},
                        {"label": "Late Delivery", "value": "late_delivery"},
                        {"label": "Changed Mind", "value": "changed_mind"},
                    ],
                }
            ],
            "tool_intent": ["list_order_items"],
        },
        "stage": "need_reason",
        "history": [case.get("customer_message", ""), "user selected order/item"],
    }


def snapshot_need_evidence(case: dict[str, Any]) -> dict[str, Any]:
    ex = case.get("extracted_fields", {})
    return {
        "slot_state": {
            "customer_identifier": ex.get("customer_id", "known_customer"),
            "selected_order_id": ex.get("order_id"),
            "selected_items": [ex.get("item_id")] if ex.get("item_id") else [],
            "reason": "damaged",
        },
        "assistant_target": {
            "assistant_message": "Please upload a photo of the item or packaging to continue.",
            "status_chip": "Awaiting Evidence",
            "next_controls": [
                {
                    "control_type": "file_upload",
                    "field": "evidence_uploaded",
                    "label": "Upload damage photo",
                }
            ],
            "tool_intent": ["upload_evidence", "validate_evidence"],
        },
        "stage": "need_evidence",
        "history": [case.get("customer_message", ""), "user selected damaged reason"],
    }


def snapshot_terminal(case: dict[str, Any]) -> dict[str, Any]:
    ex = case.get("extracted_fields", {})
    decision = case.get("policy_decision", {})
    reason = normalize_reason(case.get("issue_type", "changed_mind"))
    action = decision.get("next_action", "request_info")
    if action in {"approve_refund", "approve_return_and_refund"}:
        msg = (
            "Refund/return initiated under policy. "
            f"Amount: {decision.get('refund_amount', '0.00')}. Are you satisfied?"
        )
    elif action == "deny":
        msg = f"This case is not eligible: {decision.get('decision_reason', 'Policy constraints')}."
    elif action == "escalate":
        msg = "This case requires specialist review. Escalation created."
    else:
        msg = "I still need more details to continue."
    return {
        "slot_state": {
            "customer_identifier": ex.get("customer_id", "known_customer"),
            "selected_order_id": ex.get("order_id"),
            "selected_items": [ex.get("item_id")] if ex.get("item_id") else [],
            "reason": reason,
        },
        "assistant_target": {
            "assistant_message": msg,
            "status_chip": terminal_status(action),
            "next_controls": [
                {
                    "control_type": "buttons",
                    "field": "satisfaction",
                    "label": "Are you satisfied with this resolution?",
                    "options": [
                        {"label": "Yes, end chat", "value": "yes"},
                        {"label": "No, continue", "value": "no"},
                    ],
                }
            ],
            "tool_intent": ["lookup_order", "get_policy", "check_eligibility", "compute_refund"],
        },
        "stage": "terminal",
        "history": [case.get("customer_message", ""), "slots complete"],
    }


def build_snapshots(case: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = [snapshot_need_identifier(case), snapshot_need_reason(case)]
    if normalize_reason(case.get("issue_type", "")) == "damaged":
        snapshots.append(snapshot_need_evidence(case))
    snapshots.append(snapshot_terminal(case))
    return snapshots


def to_sft_record(case: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, str]:
    prompt = (
        "You are a stateful customer-support refund/returns assistant.\n"
        "Given conversation state, produce the next assistant step as strict JSON with keys:\n"
        "assistant_message, status_chip, next_controls, tool_intent.\n"
        f"case_id: {case.get('case_id')}\n"
        f"stage: {snapshot['stage']}\n"
        f"history: {render_json({'history': snapshot['history']})}\n"
        f"slot_state: {render_json(snapshot['slot_state'])}\n"
    )
    completion = render_json(snapshot["assistant_target"])
    text = f"<|user|>\n{prompt}\n<|assistant|>\n{completion}"
    return {"source": "conversation_synthetic", "text": text}


def to_dpo_pair(case: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "Select the next response for this customer-support chat turn.\n"
        f"case_id: {case.get('case_id')}\n"
        f"stage: {snapshot['stage']}\n"
        f"slot_state: {render_json(snapshot['slot_state'])}\n"
    )
    chosen = snapshot["assistant_target"]
    rejected = {
        "assistant_message": "Approved refund immediately without checks.",
        "status_chip": "Resolved",
        "next_controls": [],
        "tool_intent": [],
    }
    if snapshot["stage"] == "terminal":
        rejected = {
            "assistant_message": "Please share your order ID first.",
            "status_chip": "Awaiting User Info",
            "next_controls": [
                {"control_type": "text", "field": "identifier", "label": "Order ID / email / phone last 4"}
            ],
            "tool_intent": [],
        }
    return {"prompt": prompt, "chosen": chosen, "rejected": rejected}


def build_records(cases: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    sft_records: list[dict[str, str]] = []
    dpo_pairs: list[dict[str, Any]] = []
    for case in cases:
        snapshots = build_snapshots(case)
        for snap in snapshots:
            sft_records.append(to_sft_record(case, snap))
            dpo_pairs.append(to_dpo_pair(case, snap))
    return sft_records, dpo_pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build multi-turn conversation SFT/DPO datasets.")
    parser.add_argument("--train-cases", type=Path, default=Path("data/processed/synthetic_cases_train.jsonl"))
    parser.add_argument("--val-cases", type=Path, default=Path("data/processed/synthetic_cases_val.jsonl"))
    parser.add_argument(
        "--output-sft-train",
        type=Path,
        default=Path("data/processed/conversation_sft_train.jsonl"),
    )
    parser.add_argument(
        "--output-sft-val",
        type=Path,
        default=Path("data/processed/conversation_sft_val.jsonl"),
    )
    parser.add_argument(
        "--output-dpo-train",
        type=Path,
        default=Path("data/processed/conversation_dpo_pairs_train.jsonl"),
    )
    parser.add_argument("--max-train", type=int, default=3000)
    parser.add_argument("--max-val", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_cases = load_jsonl(args.train_cases, limit=args.max_train)
    val_cases = load_jsonl(args.val_cases, limit=args.max_val)

    sft_train, dpo_train = build_records(train_cases)
    sft_val, _ = build_records(val_cases)

    write_jsonl(args.output_sft_train, sft_train)
    write_jsonl(args.output_sft_val, sft_val)
    write_jsonl(args.output_dpo_train, dpo_train)

    print(
        json.dumps(
            {
                "train_cases": len(train_cases),
                "val_cases": len(val_cases),
                "sft_train_rows": len(sft_train),
                "sft_val_rows": len(sft_val),
                "dpo_train_rows": len(dpo_train),
                "outputs": {
                    "sft_train": str(args.output_sft_train),
                    "sft_val": str(args.output_sft_val),
                    "dpo_train": str(args.output_dpo_train),
                },
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
