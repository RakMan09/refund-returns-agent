from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AttachmentMeta(BaseModel):
    name: str
    mime_type: str | None = None
    size_bytes: int | None = None


class ConversationTurn(BaseModel):
    role: Literal["customer", "agent"]
    text: str
    timestamp: datetime | None = None


class AgentRequest(BaseModel):
    case_id: str
    customer_message: str
    conversation: list[ConversationTurn] = Field(default_factory=list)
    attachments: list[AttachmentMeta] = Field(default_factory=list)
    order_id: str | None = None
    email: str | None = None
    phone_last4: str | None = Field(default=None, min_length=4, max_length=4)
    reason: Literal[
        "damaged",
        "defective",
        "wrong_item",
        "not_as_described",
        "changed_mind",
        "late_delivery",
    ] | None = None


class ToolTrace(BaseModel):
    tool_name: str
    request: dict
    response: dict | None = None
    status: Literal["ok", "error", "skipped"]
    note: str | None = None


class AgentResponse(BaseModel):
    customer_reply: str
    internal_case_summary: str
    next_action_plan: str
    final_action: Literal[
        "approve_return_and_refund",
        "approve_refund",
        "request_info",
        "deny",
        "escalate",
        "refuse",
    ]
    tool_trace: list[ToolTrace]


class ChatControl(BaseModel):
    control_type: Literal["dropdown", "multiselect", "buttons", "file_upload", "text"]
    field: str
    label: str
    options: list[dict[str, str]] = Field(default_factory=list)


class ChatStartRequest(BaseModel):
    customer_identifier: str | None = None


class ChatStartResponse(BaseModel):
    session_id: str
    case_id: str
    assistant_message: str
    status_chip: str
    controls: list[ChatControl]


class ChatMessageRequest(BaseModel):
    session_id: str
    text: str = ""
    selected_order_id: str | None = None
    selected_item_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    evidence_uploaded: bool = False
    evidence_file_name: str | None = None
    evidence_mime_type: str | None = None
    evidence_size_bytes: int | None = None
    evidence_content_base64: str | None = None
    satisfaction: Literal["yes", "no"] | None = None


class ChatMessageResponse(BaseModel):
    session_id: str
    case_id: str
    assistant_message: str
    status_chip: str
    controls: list[ChatControl]
    timeline: list[dict[str, Any]]


class CreateTestOrderRequest(BaseModel):
    customer_email: str
    customer_phone_last4: str = Field(min_length=4, max_length=4)
    product_name: str
    quantity: int = Field(default=1, ge=1, le=20)
    price: Decimal = Field(default=Decimal("49.99"))
    shipping_fee: Decimal = Field(default=Decimal("5.00"))
    status: Literal["processing", "shipped", "delivered"] = "processing"
    item_category: str = "electronics"
    delivery_date: str | None = None


class CreateTestOrderResponse(BaseModel):
    order_id: str
