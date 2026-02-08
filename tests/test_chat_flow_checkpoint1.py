from services.agent_server.app.chat_flow import ChatFlowManager
from services.agent_server.app.schemas import ChatMessageRequest, ChatStartRequest


class FakeTools:
    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.order_status = "delivered"
        self.evidence_counter = 0

    def create_session(self, payload):
        self.sessions[payload["session_id"]] = {
            "session_id": payload["session_id"],
            "case_id": payload["case_id"],
            "state": payload["state"],
            "status": payload["status"],
        }
        return self.sessions[payload["session_id"]]

    def get_session(self, payload):
        return self.sessions[payload["session_id"]]

    def update_session_state(self, payload):
        s = self.sessions[payload["session_id"]]
        s["state"].update(payload["state_patch"])
        if payload.get("status"):
            s["status"] = payload["status"]
        return s

    def append_chat_message(self, payload):
        return {"ok": True}

    def list_orders(self, payload):
        return {
            "orders": [
                {
                    "order_id": "ORD-1001",
                    "status": self.order_status,
                    "order_date": "2025-12-01",
                    "delivery_date": "2025-12-05",
                }
            ]
        }

    def list_order_items(self, payload):
        return {
            "items": [
                {
                    "item_id": "ITEM-1",
                    "item_category": "electronics",
                    "item_price": "120.00",
                    "shipping_fee": "10.00",
                }
            ]
        }

    def set_selected_order(self, payload):
        s = self.sessions[payload["session_id"]]
        s["state"]["selected_order_id"] = payload["order_id"]
        return s

    def set_selected_items(self, payload):
        s = self.sessions[payload["session_id"]]
        s["state"]["selected_items"] = payload["item_ids"]
        return s

    def lookup_order(self, payload):
        return {
            "found": True,
            "order": {
                "order_id": "ORD-1001",
                "merchant_id": "M-1",
                "customer_email_masked": "al***@example.com",
                "customer_phone_last4": "1234",
                "item_id": "ITEM-1",
                "item_category": "electronics",
                "order_date": "2025-12-01",
                "delivery_date": "2025-12-05",
                "item_price": "120.00",
                "shipping_fee": "10.00",
                "status": self.order_status,
            },
        }

    def get_policy(self, payload):
        return {
            "return_window_days": 15,
            "refund_shipping": True,
            "requires_evidence_for": ["damaged", "defective", "wrong_item"],
            "non_returnable_categories": ["perishable", "personal_care"],
        }

    def check_eligibility(self, payload):
        return {
            "eligible": True,
            "missing_info": [],
            "required_evidence": [],
            "decision_reason": "Eligible under policy",
        }

    def compute_refund(self, payload):
        return {
            "amount": "130.00",
            "breakdown": {"item": "120.00", "shipping": "10.00"},
            "refund_type": "full",
        }

    def create_return(self, payload):
        return {"rma_id": "RMA-1"}

    def create_label(self, payload):
        return {"label_id": "LBL-1", "url": "https://labels.local/LBL-1.pdf"}

    def create_escalation(self, payload):
        return {"ticket_id": "ESC-1"}

    def get_case_status(self, payload):
        return {"status": "pending_refund", "eta": "2-5 business days", "refund_tracking": "TRACK-1"}

    def upload_evidence(self, payload):
        self.evidence_counter += 1
        return {
            "evidence_id": f"EVD-{self.evidence_counter}",
            "stored_path": f"/tmp/evidence/{self.evidence_counter}.jpg",
        }

    def validate_evidence(self, payload):
        return {
            "passed": True,
            "confidence": "0.810",
            "reasons": ["Image MIME type accepted", "Evidence considered sufficient for policy requirement"],
            "approach": "approach_b_simulation",
        }

    def get_evidence(self, payload):
        return {
            "evidence": [
                {
                    "evidence_id": "EVD-1",
                    "session_id": "SES-1",
                    "case_id": payload["case_id"],
                    "file_name": "damage.jpg",
                    "mime_type": "image/jpeg",
                    "size_bytes": 25000,
                    "uploaded_at": "2026-02-08T20:00:00+00:00",
                }
            ]
        }



def test_chat_start_and_identifier_prompt():
    flow = ChatFlowManager(FakeTools())
    start = flow.start(ChatStartRequest())
    assert start.session_id.startswith("SES-")
    assert start.status_chip == "Awaiting User Info"


def test_chat_flow_guided_controls():
    tools = FakeTools()
    flow = ChatFlowManager(tools)
    start = flow.start(ChatStartRequest(customer_identifier="alice@example.com"))

    step1 = flow.message(ChatMessageRequest(session_id=start.session_id, text="I want a refund"))
    assert any(c.control_type == "dropdown" for c in step1.controls)

    step2 = flow.message(
        ChatMessageRequest(session_id=start.session_id, text="", selected_order_id="ORD-1001")
    )
    assert any(c.control_type == "multiselect" for c in step2.controls)


def test_unsatisfied_branch_offers_alternatives():
    tools = FakeTools()
    flow = ChatFlowManager(tools)
    start = flow.start(ChatStartRequest(customer_identifier="alice@example.com"))

    out = flow.message(ChatMessageRequest(session_id=start.session_id, text="", satisfaction="no"))
    assert out.status_chip == "Awaiting User Choice"
    assert any(c.field == "reason" for c in out.controls)


def test_status_message_path():
    tools = FakeTools()
    flow = ChatFlowManager(tools)
    start = flow.start(ChatStartRequest(customer_identifier="alice@example.com"))
    out = flow.message(ChatMessageRequest(session_id=start.session_id, text="status"))
    assert "Case status:" in out.assistant_message


def test_cancel_when_processing_can_resolve():
    tools = FakeTools()
    tools.order_status = "processing"
    flow = ChatFlowManager(tools)
    start = flow.start(ChatStartRequest(customer_identifier="alice@example.com"))

    flow.message(ChatMessageRequest(session_id=start.session_id, text="", selected_order_id="ORD-1001"))
    flow.message(ChatMessageRequest(session_id=start.session_id, text="", selected_item_ids=["ITEM-1"]))
    out = flow.message(ChatMessageRequest(session_id=start.session_id, text="cancel order", reason="cancel_order"))
    assert out.status_chip in {"Resolved", "Awaiting User Choice"}


def test_damaged_flow_requires_and_validates_evidence():
    tools = FakeTools()
    flow = ChatFlowManager(tools)
    start = flow.start(ChatStartRequest(customer_identifier="alice@example.com"))

    flow.message(ChatMessageRequest(session_id=start.session_id, text="", selected_order_id="ORD-1001"))
    flow.message(ChatMessageRequest(session_id=start.session_id, text="", selected_item_ids=["ITEM-1"]))

    needs_upload = flow.message(ChatMessageRequest(session_id=start.session_id, text="damaged"))
    assert needs_upload.status_chip == "Awaiting Evidence"
    assert any(c.control_type == "file_upload" for c in needs_upload.controls)

    out = flow.message(
        ChatMessageRequest(
            session_id=start.session_id,
            text="uploaded evidence",
            reason="damaged",
            evidence_uploaded=True,
            evidence_file_name="damage.jpg",
            evidence_mime_type="image/jpeg",
            evidence_size_bytes=25000,
            evidence_content_base64="aGVsbG9fZXZpZGVuY2VfZmlsZQ==",
        )
    )
    assert out.status_chip in {"Refund Pending", "Resolved"}
