from __future__ import annotations

import argparse
import base64
import json
import time
from typing import Any

import httpx


def wait_for_health(url: str, timeout_s: int = 90) -> None:
    deadline = time.time() + timeout_s
    last_error = "unknown_error"
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    payload = res.json()
                    if payload.get("status") == "ok":
                        return
                last_error = f"bad_status_{res.status_code}"
        except Exception as exc:  # pragma: no cover - runtime network branch
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"health_check_timeout: {url} ({last_error})")


def send_message(agent_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(f"{agent_url.rstrip('/')}/chat/message", json=payload)
        res.raise_for_status()
        return res.json()


def choose_control(response: dict[str, Any], field: str) -> str:
    for control in response.get("controls", []):
        if control.get("field") == field:
            options = control.get("options", [])
            if not options:
                raise RuntimeError(f"control_no_options_{field}")
            return options[0]["value"]
    raise RuntimeError(f"control_not_found_{field}")


def run_chat_flow(agent_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        start = client.post(f"{agent_url.rstrip('/')}/chat/start", json={})
        start.raise_for_status()
        start_payload = start.json()

    session_id = start_payload["session_id"]
    msg1 = send_message(agent_url, {"session_id": session_id, "text": "alice@example.com"})
    order_id = choose_control(msg1, "selected_order_id")

    msg2 = send_message(
        agent_url,
        {"session_id": session_id, "text": "", "selected_order_id": order_id},
    )
    item_id = choose_control(msg2, "selected_item_ids")

    msg3 = send_message(
        agent_url,
        {"session_id": session_id, "text": "", "selected_item_ids": [item_id]},
    )
    reason = choose_control(msg3, "reason")
    if reason != "damaged":
        reason = "damaged"

    msg4 = send_message(
        agent_url,
        {"session_id": session_id, "text": reason, "reason": reason},
    )
    if msg4.get("status_chip") != "Awaiting Evidence":
        raise RuntimeError("expected_awaiting_evidence")

    raw = b"damage_" + (b"x" * 20000)
    b64 = base64.b64encode(raw).decode("utf-8")
    msg5 = send_message(
        agent_url,
        {
            "session_id": session_id,
            "text": "uploaded evidence",
            "reason": "damaged",
            "evidence_uploaded": True,
            "evidence_file_name": "damage_proof.jpg",
            "evidence_mime_type": "image/jpeg",
            "evidence_size_bytes": len(raw),
            "evidence_content_base64": b64,
        },
    )
    return msg5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test full docker stack chat flow.")
    parser.add_argument("--agent-url", default="http://localhost:8002")
    parser.add_argument("--tool-url", default="http://localhost:8001")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wait_for_health(f"{args.tool_url.rstrip('/')}/health")
    wait_for_health(f"{args.agent_url.rstrip('/')}/health")

    last = run_chat_flow(args.agent_url)
    status_chip = last.get("status_chip")
    timeline_events = [x.get("event") for x in last.get("timeline", [])]

    if status_chip not in {"Refund Pending", "Denied"}:
        raise RuntimeError(f"unexpected_terminal_status: {status_chip}")
    for required in ["Evidence uploaded", "Evidence validated", "Resolution"]:
        if required not in timeline_events:
            raise RuntimeError(f"missing_timeline_event: {required}")

    print(
        json.dumps(
            {
                "status": "ok",
                "final_status_chip": status_chip,
                "timeline_events": timeline_events,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
