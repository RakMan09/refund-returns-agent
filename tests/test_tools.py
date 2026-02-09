import os
from base64 import b64encode
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# isolated sqlite DB for tool-server tests
DB_PATH = Path("/tmp/policyllm_support_bot_test.db")
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_PATH}"

from services.tool_server.app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_lookup_order_found(client: TestClient):
    response = client.post("/tools/lookup_order", json={"order_id": "ORD-1001"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["order"]["customer_email_masked"].startswith("al")


def test_create_return_idempotent(client: TestClient):
    body = {"order_id": "ORD-1001", "item_id": "ITEM-1", "method": "dropoff"}
    r1 = client.post("/tools/create_return", json=body)
    r2 = client.post("/tools/create_return", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["rma_id"] == r2.json()["rma_id"]


def test_create_replacement_idempotent(client: TestClient):
    body = {"order_id": "ORD-1001", "item_id": "ITEM-1"}
    r1 = client.post("/tools/create_replacement", json=body)
    r2 = client.post("/tools/create_replacement", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["replacement_id"] == r2.json()["replacement_id"]


def test_list_orders_and_items(client: TestClient):
    orders = client.post("/tools/list_orders", json={"customer_identifier": "alice@example.com"})
    assert orders.status_code == 200
    assert len(orders.json()["orders"]) >= 1
    oid = orders.json()["orders"][0]["order_id"]

    items = client.post("/tools/list_order_items", json={"order_id": oid})
    assert items.status_code == 200
    assert len(items.json()["items"]) >= 1

    all_orders = client.post("/tools/list_all_orders", json={"limit": 200})
    assert all_orders.status_code == 200
    assert len(all_orders.json()["orders"]) >= 1


def test_session_tools_and_test_order(client: TestClient):
    session_id = "SES-TEST-1"
    create = client.post(
        "/tools/create_session",
        json={"session_id": session_id, "case_id": "CASE-1", "state": {"stage": "start"}, "status": "active"},
    )
    assert create.status_code == 200

    set_order = client.post(
        "/tools/set_selected_order",
        json={"session_id": session_id, "order_id": "ORD-1001"},
    )
    assert set_order.status_code == 200
    assert set_order.json()["state"]["selected_order_id"] == "ORD-1001"

    append_user = client.post(
        "/tools/append_chat_message",
        json={"session_id": session_id, "role": "user", "content": "hello"},
    )
    append_assistant = client.post(
        "/tools/append_chat_message",
        json={"session_id": session_id, "role": "assistant", "content": "hi"},
    )
    assert append_user.status_code == 200
    assert append_assistant.status_code == 200

    history = client.post("/tools/get_chat_messages", json={"session_id": session_id, "limit": 10})
    assert history.status_code == 200
    assert len(history.json()["messages"]) >= 2

    test_order = client.post(
        "/tools/create_test_order",
        json={
            "customer_email": "new@example.com",
            "customer_phone_last4": "9999",
            "product_name": "Test",
            "quantity": 1,
            "item_category": "electronics",
            "price": "21.99",
            "shipping_fee": "2.00",
            "delivery_date": None,
        },
    )
    assert test_order.status_code == 200
    order_id = test_order.json()["order_id"]
    assert order_id.startswith("ORD-")

    lookup = client.post("/tools/lookup_order", json={"order_id": order_id})
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["found"] is True
    assert body["order"]["status"] == "delivered"
    assert body["order"]["delivery_date"] is not None


def test_evidence_tools(client: TestClient):
    session_id = "SES-EVIDENCE-1"
    create = client.post(
        "/tools/create_session",
        json={"session_id": session_id, "case_id": "CASE-EVD-1", "state": {"stage": "start"}, "status": "active"},
    )
    assert create.status_code == 200

    raw = b"simulated-image-bytes"
    upload = client.post(
        "/tools/upload_evidence",
        json={
            "session_id": session_id,
            "file_name": "damage.jpg",
            "mime_type": "image/jpeg",
            "size_bytes": len(raw),
            "content_base64": b64encode(raw).decode("utf-8"),
        },
    )
    assert upload.status_code == 200
    evidence_id = upload.json()["evidence_id"]

    evidence = client.post("/tools/get_evidence", json={"case_id": "CASE-EVD-1"})
    assert evidence.status_code == 200
    assert any(r["evidence_id"] == evidence_id for r in evidence.json()["evidence"])

    validate = client.post(
        "/tools/validate_evidence",
        json={"evidence_id": evidence_id, "order_id": "ORD-1001", "item_id": "ITEM-1"},
    )
    assert validate.status_code == 200
    assert "confidence" in validate.json()


def test_case_status_for_replacement_session(client: TestClient):
    session_id = "SES-STATUS-1"
    case_id = "CASE-STATUS-1"
    create = client.post(
        "/tools/create_session",
        json={
            "session_id": session_id,
            "case_id": case_id,
            "state": {"stage": "terminal_wait"},
            "status": "pending_replacement",
        },
    )
    assert create.status_code == 200

    status = client.post("/tools/get_case_status", json={"case_id": case_id})
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "pending_replacement"
    assert body["eta"] == "3-7 business days"
    assert body["refund_tracking"].startswith("REPL-")
