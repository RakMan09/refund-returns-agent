from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

TERMINAL_STATUS_CHIPS = {
    "Resolved",
    "Refund Pending",
    "Replacement Initiated",
    "Escalated",
    "Denied",
}


def _damage_b64() -> str:
    payload = b"damage_" + (b"x" * 20000)
    return base64.b64encode(payload).decode("utf-8")


DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "id": "conv_refund",
        "description": "Refund path with full slot collection",
        "actions": [
            {"type": "text", "value": "alice@example.com"},
            {"type": "select_control", "field": "selected_order_id", "mode": "first"},
            {"type": "select_control", "field": "selected_item_ids", "mode": "first"},
            {"type": "reason", "value": "changed_mind"},
        ],
        "required_slots": ["identifier", "order", "items", "reason"],
        "expected_statuses": ["Refund Pending", "Denied"],
        "evidence_required": False,
    },
    {
        "id": "conv_damaged",
        "description": "Damaged item path with evidence upload and validation",
        "actions": [
            {"type": "text", "value": "alice@example.com"},
            {"type": "select_control", "field": "selected_order_id", "mode": "first"},
            {"type": "select_control", "field": "selected_item_ids", "mode": "first"},
            {"type": "reason", "value": "damaged"},
            {
                "type": "upload_evidence",
                "file_name": "damage_proof.jpg",
                "mime_type": "image/jpeg",
                "content_base64": _damage_b64(),
            },
        ],
        "required_slots": ["identifier", "order", "items", "reason"],
        "expected_statuses": ["Refund Pending"],
        "evidence_required": True,
    },
    {
        "id": "conv_escalate",
        "description": "Unsatisfied user asks for escalation",
        "actions": [
            {"type": "text", "value": "alice@example.com"},
            {"type": "select_control", "field": "selected_order_id", "mode": "first"},
            {"type": "select_control", "field": "selected_item_ids", "mode": "first"},
            {"type": "reason", "value": "changed_mind"},
            {"type": "satisfaction", "value": "no"},
            {"type": "reason", "value": "escalate"},
        ],
        "required_slots": ["identifier", "order", "items", "reason"],
        "expected_statuses": ["Escalated"],
        "evidence_required": False,
    },
]


def is_terminal_status(status_chip: str) -> bool:
    return status_chip in TERMINAL_STATUS_CHIPS


def extract_control_value(
    controls: list[dict[str, Any]],
    field: str,
    mode: str,
) -> str | list[str]:
    for control in controls:
        if control.get("field") != field:
            continue
        options = control.get("options", [])
        if not options:
            raise ValueError(f"control_{field}_has_no_options")
        if mode == "first":
            value = options[0]["value"]
            if field == "selected_item_ids":
                return [value]
            return value
        if mode == "all":
            values = [o["value"] for o in options]
            if field == "selected_item_ids":
                return values
            return values[0]
        raise ValueError(f"unsupported_mode_{mode}")
    raise ValueError(f"control_not_found_{field}")


def start_chat(agent_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        response = client.post(f"{agent_url.rstrip('/')}/chat/start", json={})
        response.raise_for_status()
        return response.json()


def send_chat(agent_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        response = client.post(f"{agent_url.rstrip('/')}/chat/message", json=payload)
        response.raise_for_status()
        return response.json()


def run_case(agent_url: str, case: dict[str, Any]) -> dict[str, Any]:
    start = start_chat(agent_url)
    session_id = start["session_id"]
    turns = 0
    responses: list[dict[str, Any]] = []
    transcript: list[dict[str, Any]] = [
        {"role": "assistant", "text": start["assistant_message"], "status_chip": start["status_chip"]}
    ]
    controls = start.get("controls", [])
    slots = {"identifier": False, "order": False, "items": False, "reason": False}

    for action in case["actions"]:
        payload: dict[str, Any] = {"session_id": session_id, "text": ""}

        if action["type"] == "text":
            payload["text"] = action["value"]
            slots["identifier"] = slots["identifier"] or ("@" in action["value"] or "ORD-" in action["value"])
        elif action["type"] == "reason":
            payload["reason"] = action["value"]
            payload["text"] = action["value"]
            if action["value"] not in {"escalate", "store_credit", "replacement"}:
                slots["reason"] = True
        elif action["type"] == "satisfaction":
            payload["satisfaction"] = action["value"]
        elif action["type"] == "select_control":
            value = extract_control_value(controls, action["field"], action.get("mode", "first"))
            if action["field"] == "selected_order_id":
                payload["selected_order_id"] = value
                slots["order"] = True
            elif action["field"] == "selected_item_ids":
                payload["selected_item_ids"] = value
                slots["items"] = True
            else:
                raise ValueError(f"unsupported_select_field_{action['field']}")
        elif action["type"] == "upload_evidence":
            content_b64 = action["content_base64"]
            size_bytes = len(base64.b64decode(content_b64))
            payload.update(
                {
                    "text": "uploaded evidence",
                    "reason": "damaged",
                    "evidence_uploaded": True,
                    "evidence_file_name": action["file_name"],
                    "evidence_mime_type": action["mime_type"],
                    "evidence_size_bytes": size_bytes,
                    "evidence_content_base64": content_b64,
                }
            )
        else:
            raise ValueError(f"unknown_action_{action['type']}")

        response = send_chat(agent_url, payload)
        responses.append(response)
        controls = response.get("controls", [])
        transcript.append({"role": "user", "payload": payload})
        transcript.append(
            {
                "role": "assistant",
                "text": response.get("assistant_message"),
                "status_chip": response.get("status_chip"),
            }
        )
        turns += 1

    if not responses:
        raise ValueError("case_has_no_responses")

    last = responses[-1]
    status_chip = last.get("status_chip", "")
    timeline = last.get("timeline", [])
    timeline_events = [x.get("event", "") for x in timeline]
    evidence_required = bool(case.get("evidence_required"))
    evidence_ok = True
    if evidence_required:
        evidence_ok = (
            "Evidence uploaded" in timeline_events
            and "Evidence validated" in timeline_events
            and any(r.get("status_chip") == "Awaiting Evidence" for r in responses)
        )

    expected_statuses = set(case.get("expected_statuses", []))
    task_success = status_chip in expected_statuses
    slot_fill_ok = all(slots.get(k, False) for k in case.get("required_slots", []))

    return {
        "case_id": case["id"],
        "description": case.get("description", ""),
        "task_success": task_success,
        "turns_to_resolution": turns,
        "slot_fill_ok": slot_fill_ok,
        "evidence_required": evidence_required,
        "evidence_ok": evidence_ok,
        "terminal_state_reached": is_terminal_status(status_chip),
        "final_status_chip": status_chip,
        "timeline_events": timeline_events,
        "transcript": transcript,
    }


def aggregate_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "task_success_rate": 0.0,
            "avg_turns_to_resolution": 0.0,
            "slot_filling_accuracy": 0.0,
            "evidence_handling_accuracy": 0.0,
            "terminal_state_rate": 0.0,
        }

    n = len(rows)
    evidence_rows = [r for r in rows if r["evidence_required"]]
    return {
        "n": n,
        "task_success_rate": round(sum(1 for r in rows if r["task_success"]) / n, 4),
        "avg_turns_to_resolution": round(mean(r["turns_to_resolution"] for r in rows), 4),
        "slot_filling_accuracy": round(sum(1 for r in rows if r["slot_fill_ok"]) / n, 4),
        "evidence_handling_accuracy": round(
            (
                sum(1 for r in evidence_rows if r["evidence_ok"]) / len(evidence_rows)
                if evidence_rows
                else 1.0
            ),
            4,
        ),
        "terminal_state_rate": round(sum(1 for r in rows if r["terminal_state_reached"]) / n, 4),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-turn conversational evaluation harness.")
    parser.add_argument("--agent-url", default="http://localhost:8002")
    parser.add_argument("--cases", type=Path, default=None, help="Optional JSON file for case list")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/results/conversation_eval_report.json"),
    )
    parser.add_argument(
        "--transcripts-output",
        type=Path,
        default=Path("eval/results/conversation_transcripts.jsonl"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = DEFAULT_CASES
    if args.cases is not None:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))

    details = [run_case(args.agent_url, case) for case in cases]
    metrics = aggregate_results(details)
    report = {"config": {"agent_url": args.agent_url, "cases": len(cases)}, "metrics": metrics, "details": details}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    with args.transcripts_output.open("w", encoding="utf-8") as fh:
        for row in details:
            payload = {
                "case_id": row["case_id"],
                "description": row["description"],
                "final_status_chip": row["final_status_chip"],
                "transcript": row["transcript"],
            }
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

    print(
        json.dumps(
            {
                "metrics": metrics,
                "output": str(args.output),
                "transcripts": str(args.transcripts_output),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
