from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

import httpx


def post(agent_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(f"{agent_url.rstrip('/')}{path}", json=payload)
        res.raise_for_status()
        return res.json()


def _first_option(response: dict[str, Any], field: str) -> str:
    for ctrl in response.get("controls", []):
        if ctrl.get("field") == field:
            return ctrl.get("options", [])[0]["value"]
    raise RuntimeError(f"missing_control:{field}")


def _start(agent_url: str) -> dict[str, Any]:
    return post(agent_url, "/chat/start", {})


def run_damaged(agent_url: str) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    s = _start(agent_url)
    sid = s["session_id"]
    out.append({"role": "assistant", "payload": s})
    m1 = post(agent_url, "/chat/message", {"session_id": sid, "text": "alice@example.com"})
    out.append({"role": "assistant", "payload": m1})
    order_id = _first_option(m1, "selected_order_id")
    m2 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_order_id": order_id})
    out.append({"role": "assistant", "payload": m2})
    item_id = _first_option(m2, "selected_item_ids")
    m3 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_item_ids": [item_id]})
    out.append({"role": "assistant", "payload": m3})
    m4 = post(agent_url, "/chat/message", {"session_id": sid, "text": "damaged", "reason": "damaged"})
    out.append({"role": "assistant", "payload": m4})
    raw = b"damage_" + (b"x" * 20000)
    b64 = base64.b64encode(raw).decode("utf-8")
    m5 = post(
        agent_url,
        "/chat/message",
        {
            "session_id": sid,
            "text": "uploaded evidence",
            "reason": "damaged",
            "evidence_uploaded": True,
            "evidence_file_name": "damage_proof.jpg",
            "evidence_mime_type": "image/jpeg",
            "evidence_size_bytes": len(raw),
            "evidence_content_base64": b64,
        },
    )
    out.append({"role": "assistant", "payload": m5})
    return {"scenario": "damaged_evidence", "session_id": sid, "messages": out}


def run_escalation(agent_url: str) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    s = _start(agent_url)
    sid = s["session_id"]
    out.append({"role": "assistant", "payload": s})
    m1 = post(agent_url, "/chat/message", {"session_id": sid, "text": "alice@example.com"})
    order_id = _first_option(m1, "selected_order_id")
    m2 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_order_id": order_id})
    item_id = _first_option(m2, "selected_item_ids")
    _ = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_item_ids": [item_id]})
    m3 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "satisfaction": "no"})
    out.extend([{"role": "assistant", "payload": m1}, {"role": "assistant", "payload": m2}, {"role": "assistant", "payload": m3}])
    m4 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "reason": "escalate"})
    out.append({"role": "assistant", "payload": m4})
    return {"scenario": "escalation", "session_id": sid, "messages": out}


def run_cancel(agent_url: str) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    create = post(
        agent_url,
        "/chat/create_test_order",
        {
            "customer_email": "cancel-demo@example.com",
            "customer_phone_last4": "2222",
            "product_name": "Cancel Demo",
            "quantity": 1,
            "item_category": "electronics",
            "price": "29.99",
            "shipping_fee": "5.00",
            "status": "processing",
            "delivery_date": None,
        },
    )
    s = _start(agent_url)
    sid = s["session_id"]
    out.append({"role": "assistant", "payload": s})
    m1 = post(agent_url, "/chat/message", {"session_id": sid, "text": "cancel-demo@example.com"})
    order_id = _first_option(m1, "selected_order_id")
    m2 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_order_id": order_id})
    item_id = _first_option(m2, "selected_item_ids")
    m3 = post(agent_url, "/chat/message", {"session_id": sid, "text": "", "selected_item_ids": [item_id]})
    m4 = post(agent_url, "/chat/message", {"session_id": sid, "text": "cancel order", "reason": "cancel_order"})
    out.extend(
        [
            {"role": "assistant", "payload": m1},
            {"role": "assistant", "payload": m2},
            {"role": "assistant", "payload": m3},
            {"role": "assistant", "payload": m4},
        ]
    )
    return {
        "scenario": "cancel_processing",
        "session_id": sid,
        "created_order_id": create["order_id"],
        "messages": out,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic demo chat scenarios.")
    parser.add_argument("--agent-url", default="http://localhost:8002")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/results/demo_scenarios.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = [
        run_damaged(args.agent_url),
        run_escalation(args.agent_url),
        run_cancel(args.agent_url),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"scenarios": results}, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "scenarios": len(results)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
