from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class LookupOrderRequest(BaseModel):
    order_id: str | None = None
    email: EmailStr | None = None
    phone_last4: str | None = Field(default=None, min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_identifier_present(self) -> "LookupOrderRequest":
        provided = [self.order_id, self.email, self.phone_last4]
        if sum(v is not None for v in provided) != 1:
            raise ValueError("Provide exactly one identifier: order_id OR email OR phone_last4")
        return self


class MaskedOrder(BaseModel):
    order_id: str
    merchant_id: str
    customer_email_masked: str
    customer_phone_last4: str
    item_id: str
    item_category: str
    order_date: date
    delivery_date: date | None
    item_price: Decimal
    shipping_fee: Decimal
    status: str


class LookupOrderResponse(BaseModel):
    order: MaskedOrder | None
    found: bool


class ListOrdersRequest(BaseModel):
    customer_identifier: str


class OrderSummary(BaseModel):
    order_id: str
    status: str
    order_date: date
    delivery_date: date | None


class ListOrdersResponse(BaseModel):
    orders: list[OrderSummary]


class ListOrderItemsRequest(BaseModel):
    order_id: str


class OrderItem(BaseModel):
    item_id: str
    item_category: str
    item_price: Decimal
    shipping_fee: Decimal


class ListOrderItemsResponse(BaseModel):
    items: list[OrderItem]


class CreateSessionRequest(BaseModel):
    session_id: str
    case_id: str
    state: dict = Field(default_factory=dict)
    status: str = "active"


class GetSessionRequest(BaseModel):
    session_id: str


class SetSelectedOrderRequest(BaseModel):
    session_id: str
    order_id: str


class SetSelectedItemsRequest(BaseModel):
    session_id: str
    item_ids: list[str]


class UpdateSessionStateRequest(BaseModel):
    session_id: str
    state_patch: dict
    status: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    case_id: str
    state: dict
    status: str


class AppendChatMessageRequest(BaseModel):
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str


class GetPolicyRequest(BaseModel):
    merchant_id: str
    item_category: str
    reason: Literal[
        "damaged",
        "defective",
        "wrong_item",
        "not_as_described",
        "changed_mind",
        "late_delivery",
    ]
    order_date: date
    delivery_date: date | None


class GetPolicyResponse(BaseModel):
    return_window_days: int
    refund_shipping: bool
    requires_evidence_for: list[str]
    non_returnable_categories: list[str]


class CheckEligibilityRequest(BaseModel):
    order: MaskedOrder
    policy: GetPolicyResponse
    reason: str


class CheckEligibilityResponse(BaseModel):
    eligible: bool
    missing_info: list[str]
    required_evidence: list[str]
    decision_reason: str


class ComputeRefundRequest(BaseModel):
    order: MaskedOrder
    policy: GetPolicyResponse
    reason: str


class ComputeRefundResponse(BaseModel):
    amount: Decimal
    breakdown: dict[str, Decimal]
    refund_type: Literal["full", "partial", "none"]


class CreateReturnRequest(BaseModel):
    order_id: str
    item_id: str
    method: Literal["dropoff", "pickup"]


class CreateReturnResponse(BaseModel):
    rma_id: str


class CreateLabelRequest(BaseModel):
    rma_id: str


class CreateLabelResponse(BaseModel):
    label_id: str
    url: str


class CreateEscalationRequest(BaseModel):
    case_id: str
    reason: str
    evidence: dict


class CreateEscalationResponse(BaseModel):
    ticket_id: str


class CreateTestOrderRequest(BaseModel):
    customer_email: EmailStr
    customer_phone_last4: str = Field(min_length=4, max_length=4)
    product_name: str
    quantity: int = Field(default=1, ge=1, le=20)
    item_category: str
    price: Decimal = Field(default=Decimal("49.99"), gt=Decimal("0"))
    shipping_fee: Decimal = Field(default=Decimal("5.00"), ge=Decimal("0"))
    status: Literal["processing", "shipped", "delivered"] = "processing"
    delivery_date: date | None = None


class CreateTestOrderResponse(BaseModel):
    order_id: str


class GetCaseStatusRequest(BaseModel):
    case_id: str


class GetCaseStatusResponse(BaseModel):
    status: str
    eta: str | None
    refund_tracking: str | None


class UploadEvidenceRequest(BaseModel):
    session_id: str
    file_name: str
    mime_type: str
    size_bytes: int = Field(ge=1, le=10_000_000)
    content_base64: str = Field(min_length=16)


class UploadEvidenceResponse(BaseModel):
    evidence_id: str
    stored_path: str


class GetEvidenceRequest(BaseModel):
    case_id: str


class EvidenceSummary(BaseModel):
    evidence_id: str
    session_id: str
    case_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    uploaded_at: str


class GetEvidenceResponse(BaseModel):
    evidence: list[EvidenceSummary]


class ValidateEvidenceRequest(BaseModel):
    evidence_id: str
    order_id: str
    item_id: str


class ValidateEvidenceResponse(BaseModel):
    passed: bool
    confidence: Decimal
    reasons: list[str]
    approach: str = "approach_b_simulation"
