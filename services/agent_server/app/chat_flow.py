from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from services.agent_server.app.guardrails import looks_like_fraud_or_exfil, looks_like_injection
from services.agent_server.app.schemas import (
    ChatControl,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatStartRequest,
    ChatStartResponse,
)
from services.agent_server.app.tool_client import ToolClient


TERMINAL_EXIT_WORDS = {"end chat", "close chat", "exit", "quit", "stop"}


def _infer_reason(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in ["damaged", "broken", "cracked"]):
        return "damaged"
    if any(k in t for k in ["defective", "not working", "replacement"]):
        return "defective"
    if "wrong item" in t or "missing item" in t:
        return "wrong_item"
    if "late" in t or "delayed" in t:
        return "late_delivery"
    if "cancel" in t:
        return "cancel_order"
    if "return" in t:
        return "return_request"
    if "changed my mind" in t:
        return "changed_mind"
    if "not as described" in t:
        return "not_as_described"
    if "refund" in t:
        return "refund_request"
    return None


def _base_state() -> dict:
    return {
        "stage": "need_identifier",
        "customer_identifier": None,
        "selected_order_id": None,
        "selected_items": [],
        "reason": None,
        "preferred_resolution": "refund",
        "evidence_uploaded": False,
        "evidence_id": None,
        "evidence_validation": None,
        "terminal": False,
        "timeline": [],
    }


class ChatFlowManager:
    def __init__(self, tools: ToolClient):
        self.tools = tools

    def start(self, req: ChatStartRequest) -> ChatStartResponse:
        session_id = f"SES-{uuid4().hex[:12]}"
        case_id = f"CASE-{uuid4().hex[:12]}"
        state = _base_state()
        state["customer_identifier"] = req.customer_identifier

        self.tools.create_session(
            {"session_id": session_id, "case_id": case_id, "state": state, "status": "active"}
        )

        controls = [
            ChatControl(
                control_type="text",
                field="identifier",
                label="Share order ID, email, or phone last 4.",
            )
        ]
        if req.customer_identifier:
            controls = []
        return ChatStartResponse(
            session_id=session_id,
            case_id=case_id,
            assistant_message=(
                "Hi, I can help with refund, return, replacement, missing/wrong item, "
                "late delivery, or cancellation."
            ),
            status_chip="Awaiting User Info",
            controls=controls,
        )

    def message(self, req: ChatMessageRequest) -> ChatMessageResponse:
        session = self.tools.get_session({"session_id": req.session_id})
        state = dict(session.get("state", {}))
        case_id = session["case_id"]

        user_text = (req.text or "").strip()
        self.tools.append_chat_message(
            {"session_id": req.session_id, "role": "user", "content": user_text or "[ui_action]"}
        )

        if user_text.lower() in TERMINAL_EXIT_WORDS:
            state["terminal"] = True
            state["stage"] = "resolved"
            self._append_timeline(state, "User ended chat", "explicit_exit")
            self._save_state(req.session_id, state, status="resolved")
            return self._resp(
                req.session_id,
                case_id,
                "Chat ended. You can restart anytime if you need further help.",
                "Resolved",
                [],
            )

        if user_text.lower() in {"status", "status check", "refund status", "case status"}:
            status = self.tools.get_case_status({"case_id": case_id})
            self._append_timeline(state, "Status check", status.get("status", "unknown"))
            self._save_state(req.session_id, state)
            msg = (
                f"Case status: {status.get('status')}. "
                f"ETA: {status.get('eta') or 'N/A'}. "
                f"Tracking: {status.get('refund_tracking') or 'N/A'}."
            )
            return self._resp(req.session_id, case_id, msg, "Status", [])

        if looks_like_fraud_or_exfil(user_text):
            msg = "I can't help with fraud, policy bypass, or data-exfiltration requests."
            self._append_timeline(state, "Guardrail refusal", "fraud_or_exfil")
            self._save_state(req.session_id, state, status="refused")
            return self._resp(req.session_id, case_id, msg, "Refused", [])

        if looks_like_injection(user_text):
            msg = "Please provide a normal support request with order/account details."
            self._append_timeline(state, "Guardrail check", "prompt_injection")
            self._save_state(req.session_id, state)
            return self._resp(
                req.session_id,
                case_id,
                msg,
                "Awaiting User Info",
                [
                    ChatControl(
                        control_type="text",
                        field="identifier",
                        label="Order ID, email, or phone last 4",
                    )
                ],
            )

        if req.satisfaction == "yes":
            state["terminal"] = True
            state["stage"] = "resolved"
            self._append_timeline(state, "User confirmed satisfaction", "resolved")
            self._save_state(req.session_id, state, status="resolved")
            return self._resp(
                req.session_id,
                case_id,
                "Great. Your case is now closed. You can start a new chat anytime.",
                "Resolved",
                [],
            )

        if req.satisfaction == "no":
            state["stage"] = "offer_alternatives"
            self._append_timeline(state, "User not satisfied", "continue")
            self._save_state(req.session_id, state)
            return self._resp(
                req.session_id,
                case_id,
                "Thanks for the feedback. Choose an alternative path.",
                "Awaiting User Choice",
                [
                    ChatControl(
                        control_type="buttons",
                        field="reason",
                        label="Alternative resolution",
                        options=[
                            {"label": "Replacement", "value": "replacement"},
                            {"label": "Store credit", "value": "store_credit"},
                            {"label": "Escalate to human", "value": "escalate"},
                        ],
                    )
                ],
            )

        if req.reason in {"replacement", "store_credit", "escalate"}:
            return self._handle_alternative(req, case_id, state)

        # Fill identifier from text if direct order ID/email/phone provided.
        if not state.get("customer_identifier") and user_text:
            if "@" in user_text or (user_text.isdigit() and len(user_text) == 4) or user_text.upper().startswith("ORD-"):
                state["customer_identifier"] = user_text

        if not state.get("customer_identifier"):
            self._save_state(req.session_id, state)
            return self._resp(
                req.session_id,
                case_id,
                "Please share order ID, email, or phone last 4 so I can list your orders.",
                "Awaiting User Info",
                [
                    ChatControl(
                        control_type="text",
                        field="identifier",
                        label="Order ID / email / phone last 4",
                    )
                ],
            )

        if req.selected_order_id:
            self.tools.set_selected_order(
                {"session_id": req.session_id, "order_id": req.selected_order_id}
            )
            state["selected_order_id"] = req.selected_order_id

        if req.selected_item_ids:
            self.tools.set_selected_items(
                {"session_id": req.session_id, "item_ids": req.selected_item_ids}
            )
            state["selected_items"] = req.selected_item_ids

        if req.reason:
            state["reason"] = req.reason

        if req.evidence_uploaded:
            state["evidence_uploaded"] = True

        if req.evidence_content_base64 and req.evidence_file_name and req.evidence_mime_type:
            upload = self.tools.upload_evidence(
                {
                    "session_id": req.session_id,
                    "file_name": req.evidence_file_name,
                    "mime_type": req.evidence_mime_type,
                    "size_bytes": req.evidence_size_bytes or 0,
                    "content_base64": req.evidence_content_base64,
                }
            )
            state["evidence_uploaded"] = True
            state["evidence_id"] = upload["evidence_id"]
            state["evidence_validation"] = None
            self._append_timeline(state, "Evidence uploaded", upload["evidence_id"])

        if not state.get("selected_order_id"):
            orders = self.tools.list_orders(
                {"customer_identifier": state["customer_identifier"]}
            ).get("orders", [])
            self._append_timeline(state, "Listed orders", f"count={len(orders)}")
            self._save_state(req.session_id, state)
            if not orders:
                return self._resp(
                    req.session_id,
                    case_id,
                    "I couldn't find orders for that identifier. Try another one.",
                    "Awaiting User Info",
                    [
                        ChatControl(
                            control_type="text",
                            field="identifier",
                            label="Order ID / email / phone last 4",
                        )
                    ],
                )
            return self._resp(
                req.session_id,
                case_id,
                "Select your order.",
                "Awaiting User Choice",
                [
                    ChatControl(
                        control_type="dropdown",
                        field="selected_order_id",
                        label="Select order",
                        options=[
                            {"label": f"{o['order_id']} ({o['status']})", "value": o["order_id"]}
                            for o in orders
                        ],
                    )
                ],
            )

        if not state.get("selected_items"):
            items = self.tools.list_order_items({"order_id": state["selected_order_id"]}).get("items", [])
            self._append_timeline(state, "Listed order items", f"count={len(items)}")
            self._save_state(req.session_id, state)
            return self._resp(
                req.session_id,
                case_id,
                "Select item(s) to continue.",
                "Awaiting User Choice",
                [
                    ChatControl(
                        control_type="multiselect",
                        field="selected_item_ids",
                        label="Select item(s)",
                        options=[
                            {
                                "label": f"{i['item_id']} ({i['item_category']})",
                                "value": i["item_id"],
                            }
                            for i in items
                        ],
                    )
                ],
            )

        if not state.get("reason"):
            inferred = _infer_reason(user_text)
            if inferred:
                state["reason"] = inferred
            else:
                self._save_state(req.session_id, state)
                return self._resp(
                    req.session_id,
                    case_id,
                    "Select the reason for your request.",
                    "Awaiting User Choice",
                    [
                        ChatControl(
                            control_type="buttons",
                            field="reason",
                            label="Reason",
                            options=[
                                {"label": "Refund Request", "value": "refund_request"},
                                {"label": "Return Request", "value": "return_request"},
                                {"label": "Replacement", "value": "defective"},
                                {"label": "Cancel Order", "value": "cancel_order"},
                                {"label": "Missing / Wrong Item", "value": "wrong_item"},
                                {"label": "Damaged", "value": "damaged"},
                                {"label": "Late Delivery", "value": "late_delivery"},
                                {"label": "Changed Mind", "value": "changed_mind"},
                            ],
                        )
                    ],
                )

        reason = self._normalize_reason(state["reason"])
        state["reason"] = reason

        if reason == "cancel_order":
            return self._handle_cancel(req, case_id, state)

        if reason == "damaged" and not state.get("evidence_uploaded"):
            self._save_state(req.session_id, state)
            return self._resp(
                req.session_id,
                case_id,
                "Please upload a photo of the item or packaging to continue.",
                "Awaiting Evidence",
                [
                    ChatControl(
                        control_type="file_upload",
                        field="evidence_uploaded",
                        label="Upload damage photo",
                    )
                ],
            )

        if reason == "damaged":
            if not state.get("evidence_id"):
                self._save_state(req.session_id, state)
                return self._resp(
                    req.session_id,
                    case_id,
                    "I still need the damage photo upload to proceed.",
                    "Awaiting Evidence",
                    [
                        ChatControl(
                            control_type="file_upload",
                            field="evidence_uploaded",
                            label="Upload damage photo",
                        )
                    ],
                )
            if not state.get("evidence_validation"):
                validation = self.tools.validate_evidence(
                    {
                        "evidence_id": state["evidence_id"],
                        "order_id": state["selected_order_id"],
                        "item_id": state["selected_items"][0],
                    }
                )
                state["evidence_validation"] = validation
                summary = (
                    f"pass={validation['passed']} confidence={validation['confidence']}"
                )
                self._append_timeline(state, "Evidence validated", summary)
                if not validation.get("passed", False):
                    self._save_state(req.session_id, state)
                    reasons = ", ".join(validation.get("reasons", []))
                    return self._resp(
                        req.session_id,
                        case_id,
                        (
                            "Evidence looks insufficient for damage verification. "
                            f"Reason(s): {reasons}. Please upload a clearer image."
                        ),
                        "Awaiting Evidence",
                        [
                            ChatControl(
                                control_type="file_upload",
                                field="evidence_uploaded",
                                label="Upload clearer damage photo",
                            )
                        ],
                    )

            evidence = self.tools.get_evidence({"case_id": case_id}).get("evidence", [])
            self._append_timeline(state, "Evidence retrieved", f"count={len(evidence)}")

        return self._handle_resolution(req, case_id, state)

    def _handle_cancel(self, req: ChatMessageRequest, case_id: str, state: dict) -> ChatMessageResponse:
        order_lookup = self.tools.lookup_order({"order_id": state["selected_order_id"]})
        order = order_lookup.get("order")
        if order["status"] in {"processing"}:
            state["stage"] = "terminal_wait"
            self._append_timeline(state, "Cancel approved", f"order={order['order_id']}")
            self._save_state(req.session_id, state, status="resolved")
            return self._resp(
                req.session_id,
                case_id,
                "Order cancellation approved because the item has not shipped yet. Are you satisfied?",
                "Resolved",
                [
                    ChatControl(
                        control_type="buttons",
                        field="satisfaction",
                        label="Are you satisfied with this resolution?",
                        options=[
                            {"label": "Yes, end chat", "value": "yes"},
                            {"label": "No, continue", "value": "no"},
                        ],
                    )
                ],
            )

        state["stage"] = "offer_alternatives"
        self._append_timeline(state, "Cancel denied", "already_shipped")
        self._save_state(req.session_id, state)
        return self._resp(
            req.session_id,
            case_id,
            "This order is already shipped/delivered. You can proceed with return or escalate.",
            "Awaiting User Choice",
            [
                ChatControl(
                    control_type="buttons",
                    field="reason",
                    label="Choose next step",
                    options=[
                        {"label": "Proceed with return", "value": "return_request"},
                        {"label": "Escalate to human", "value": "escalate"},
                    ],
                )
            ],
        )

    def _handle_alternative(self, req: ChatMessageRequest, case_id: str, state: dict) -> ChatMessageResponse:
        if req.reason == "replacement":
            state["stage"] = "terminal_wait"
            self._append_timeline(state, "Alternative selected", "replacement")
            self._save_state(req.session_id, state, status="pending_replacement")
            return self._resp(
                req.session_id,
                case_id,
                "Replacement has been initiated. You'll receive shipment details shortly. Are you satisfied?",
                "Replacement Initiated",
                [
                    ChatControl(
                        control_type="buttons",
                        field="satisfaction",
                        label="Are you satisfied with this resolution?",
                        options=[
                            {"label": "Yes, end chat", "value": "yes"},
                            {"label": "No, continue", "value": "no"},
                        ],
                    )
                ],
            )

        if req.reason == "store_credit":
            state["stage"] = "terminal_wait"
            self._append_timeline(state, "Alternative selected", "store_credit")
            self._save_state(req.session_id, state, status="resolved")
            return self._resp(
                req.session_id,
                case_id,
                "Store credit option selected. Credit will be applied within 24 hours. Are you satisfied?",
                "Resolved",
                [
                    ChatControl(
                        control_type="buttons",
                        field="satisfaction",
                        label="Are you satisfied with this resolution?",
                        options=[
                            {"label": "Yes, end chat", "value": "yes"},
                            {"label": "No, continue", "value": "no"},
                        ],
                    )
                ],
            )

        if req.reason == "escalate":
            ticket = self.tools.create_escalation(
                {
                    "case_id": case_id,
                    "reason": "customer_not_satisfied",
                    "evidence": {"note": "escalated from chat flow"},
                }
            )
            state["stage"] = "terminal_wait"
            self._append_timeline(state, "Escalated", ticket["ticket_id"])
            self._save_state(req.session_id, state, status="escalated")
            return self._resp(
                req.session_id,
                case_id,
                f"Escalation created: {ticket['ticket_id']}. A specialist will follow up. Are you satisfied?",
                "Escalated",
                [
                    ChatControl(
                        control_type="buttons",
                        field="satisfaction",
                        label="Are you satisfied with this resolution?",
                        options=[
                            {"label": "Yes, end chat", "value": "yes"},
                            {"label": "No, continue", "value": "no"},
                        ],
                    )
                ],
            )

        # fallback
        self._save_state(req.session_id, state)
        return self._resp(req.session_id, case_id, "Please choose an available option.", "Awaiting User Choice", [])

    def _normalize_reason(self, reason: str) -> str:
        mapping = {
            "refund_request": "changed_mind",
            "return_request": "changed_mind",
            "missing_item": "wrong_item",
        }
        return mapping.get(reason, reason)

    def _handle_resolution(self, req: ChatMessageRequest, case_id: str, state: dict) -> ChatMessageResponse:
        order_lookup = self.tools.lookup_order({"order_id": state["selected_order_id"]})
        order = order_lookup.get("order")
        policy = self.tools.get_policy(
            {
                "merchant_id": order["merchant_id"],
                "item_category": order["item_category"],
                "reason": state["reason"],
                "order_date": order["order_date"],
                "delivery_date": order.get("delivery_date"),
            }
        )
        eligibility = self.tools.check_eligibility(
            {"order": order, "policy": policy, "reason": state["reason"]}
        )

        if not eligibility.get("eligible", False):
            state["stage"] = "terminal_wait"
            self._append_timeline(state, "Decision", eligibility.get("decision_reason", "deny"))
            self._save_state(req.session_id, state, status="resolved")
            return self._resp(
                req.session_id,
                case_id,
                f"This case is not eligible: {eligibility.get('decision_reason')}. Are you satisfied?",
                "Denied",
                [
                    ChatControl(
                        control_type="buttons",
                        field="satisfaction",
                        label="Are you satisfied with this resolution?",
                        options=[
                            {"label": "Yes, end chat", "value": "yes"},
                            {"label": "No, continue", "value": "no"},
                        ],
                    )
                ],
            )

        refund = self.tools.compute_refund(
            {"order": order, "policy": policy, "reason": state["reason"]}
        )
        ret = self.tools.create_return(
            {"order_id": order["order_id"], "item_id": order["item_id"], "method": "dropoff"}
        )
        label = self.tools.create_label({"rma_id": ret["rma_id"]})
        state["stage"] = "terminal_wait"
        self._append_timeline(state, "Resolution", f"refund={refund['amount']} rma={ret['rma_id']}")
        self._save_state(req.session_id, state, status="pending_refund")
        return self._resp(
            req.session_id,
            case_id,
            (
                "Refund/return initiated. "
                f"Amount: {refund['amount']}. RMA: {ret['rma_id']}. "
                f"Label: {label['url']}. Are you satisfied?"
            ),
            "Refund Pending",
            [
                ChatControl(
                    control_type="buttons",
                    field="satisfaction",
                    label="Are you satisfied with this resolution?",
                    options=[
                        {"label": "Yes, end chat", "value": "yes"},
                        {"label": "No, continue", "value": "no"},
                    ],
                )
            ],
        )

    def _save_state(self, session_id: str, state: dict, status: str | None = None) -> None:
        payload = {"session_id": session_id, "state_patch": state, "status": status}
        self.tools.update_session_state(payload)

    def _append_timeline(self, state: dict, event: str, detail: str) -> None:
        timeline = list(state.get("timeline", []))
        timeline.append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "detail": detail,
            }
        )
        state["timeline"] = timeline

    def _resp(
        self,
        session_id: str,
        case_id: str,
        message: str,
        status_chip: str,
        controls: list[ChatControl],
    ) -> ChatMessageResponse:
        self.tools.append_chat_message({"session_id": session_id, "role": "assistant", "content": message})
        session = self.tools.get_session({"session_id": session_id})
        return ChatMessageResponse(
            session_id=session_id,
            case_id=case_id,
            assistant_message=message,
            status_chip=status_chip,
            controls=controls,
            timeline=session.get("state", {}).get("timeline", []),
        )
