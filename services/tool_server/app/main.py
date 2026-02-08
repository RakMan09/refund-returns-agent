import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse

from services.tool_server.app.config import settings
from services.tool_server.app.policy_engine import check_eligibility, compute_refund, get_policy
from services.tool_server.app.repository import Repository, mask_email
from services.tool_server.app.schemas import (
    AppendChatMessageRequest,
    CheckEligibilityRequest,
    CheckEligibilityResponse,
    ComputeRefundRequest,
    ComputeRefundResponse,
    CreateEscalationRequest,
    CreateEscalationResponse,
    CreateLabelRequest,
    CreateLabelResponse,
    CreateReturnRequest,
    CreateReturnResponse,
    CreateSessionRequest,
    CreateTestOrderRequest,
    CreateTestOrderResponse,
    GetEvidenceRequest,
    GetEvidenceResponse,
    GetCaseStatusRequest,
    GetCaseStatusResponse,
    GetPolicyRequest,
    GetPolicyResponse,
    GetSessionRequest,
    ListOrderItemsRequest,
    ListOrderItemsResponse,
    ListOrdersRequest,
    ListOrdersResponse,
    LookupOrderRequest,
    LookupOrderResponse,
    MaskedOrder,
    OrderItem,
    OrderSummary,
    SessionResponse,
    SetSelectedItemsRequest,
    SetSelectedOrderRequest,
    UploadEvidenceRequest,
    UploadEvidenceResponse,
    UpdateSessionStateRequest,
    ValidateEvidenceRequest,
    ValidateEvidenceResponse,
)

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("tool_server")

repo = Repository(
    settings.database_url,
    evidence_storage_dir=settings.evidence_storage_dir,
    approach_b_catalog_dir=settings.approach_b_catalog_dir,
    approach_b_anomaly_dir=settings.approach_b_anomaly_dir,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    repo.create_tables()
    yield


app = FastAPI(title="refund-returns-tool-server", lifespan=lifespan)

ReqT = TypeVar("ReqT", bound=BaseModel)
ResT = TypeVar("ResT", bound=BaseModel)


def run_with_logging(tool_name: str, request: BaseModel, fn: Callable[[], ResT]) -> ResT:
    start = time.perf_counter()
    request_payload = request.model_dump(mode="json")
    try:
        response = fn()
        latency_ms = int((time.perf_counter() - start) * 1000)
        repo.log_tool_call(
            tool_name=tool_name,
            request_payload=request_payload,
            response_payload=response.model_dump(mode="json"),
            error_message=None,
            latency_ms=latency_ms,
        )
        logger.info(
            "tool_call_success tool=%s latency_ms=%s request=%s",
            tool_name,
            latency_ms,
            request_payload,
        )
        return response
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        repo.log_tool_call(
            tool_name=tool_name,
            request_payload=request_payload,
            response_payload=None,
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        logger.exception("tool_call_error tool=%s latency_ms=%s", tool_name, latency_ms)
        raise


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tools/lookup_order", response_model=LookupOrderResponse)
def lookup_order(request: LookupOrderRequest) -> LookupOrderResponse:
    def _run() -> LookupOrderResponse:
        row = repo.lookup_order(order_id=request.order_id, email=request.email, phone_last4=request.phone_last4)
        if row is None:
            return LookupOrderResponse(order=None, found=False)

        masked_order = MaskedOrder(
            order_id=row.order_id,
            merchant_id=row.merchant_id,
            customer_email_masked=mask_email(row.customer_email),
            customer_phone_last4=row.customer_phone_last4,
            item_id=row.item_id,
            item_category=row.item_category,
            order_date=row.order_date,
            delivery_date=row.delivery_date,
            item_price=row.item_price,
            shipping_fee=row.shipping_fee,
            status=row.status,
        )
        return LookupOrderResponse(order=masked_order, found=True)

    return run_with_logging("lookup_order", request, _run)


@app.post("/tools/list_orders", response_model=ListOrdersResponse)
def list_orders(request: ListOrdersRequest) -> ListOrdersResponse:
    def _run() -> ListOrdersResponse:
        rows = repo.list_orders(request.customer_identifier)
        return ListOrdersResponse(
            orders=[
                OrderSummary(
                    order_id=r.order_id,
                    status=r.status,
                    order_date=r.order_date,
                    delivery_date=r.delivery_date,
                )
                for r in rows
            ]
        )

    return run_with_logging("list_orders", request, _run)


@app.post("/tools/list_order_items", response_model=ListOrderItemsResponse)
def list_order_items(request: ListOrderItemsRequest) -> ListOrderItemsResponse:
    def _run() -> ListOrderItemsResponse:
        rows = repo.list_order_items(request.order_id)
        return ListOrderItemsResponse(
            items=[
                OrderItem(
                    item_id=r.item_id,
                    item_category=r.item_category,
                    item_price=r.item_price,
                    shipping_fee=r.shipping_fee,
                )
                for r in rows
            ]
        )

    return run_with_logging("list_order_items", request, _run)


@app.post("/tools/create_session", response_model=SessionResponse)
def create_session(request: CreateSessionRequest) -> SessionResponse:
    def _run() -> SessionResponse:
        s = repo.create_session(request.session_id, request.case_id, request.state, request.status)
        return SessionResponse(session_id=s.session_id, case_id=s.case_id, state=s.state_json, status=s.status)

    return run_with_logging("create_session", request, _run)


@app.post("/tools/get_session", response_model=SessionResponse)
def get_session(request: GetSessionRequest) -> SessionResponse:
    def _run() -> SessionResponse:
        s = repo.get_session(request.session_id)
        if s is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        return SessionResponse(session_id=s.session_id, case_id=s.case_id, state=s.state_json, status=s.status)

    return run_with_logging("get_session", request, _run)


@app.post("/tools/set_selected_order", response_model=SessionResponse)
def set_selected_order(request: SetSelectedOrderRequest) -> SessionResponse:
    def _run() -> SessionResponse:
        s = repo.update_session_state(request.session_id, {"selected_order_id": request.order_id})
        if s is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        return SessionResponse(session_id=s.session_id, case_id=s.case_id, state=s.state_json, status=s.status)

    return run_with_logging("set_selected_order", request, _run)


@app.post("/tools/set_selected_items", response_model=SessionResponse)
def set_selected_items(request: SetSelectedItemsRequest) -> SessionResponse:
    def _run() -> SessionResponse:
        s = repo.update_session_state(request.session_id, {"selected_items": request.item_ids})
        if s is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        return SessionResponse(session_id=s.session_id, case_id=s.case_id, state=s.state_json, status=s.status)

    return run_with_logging("set_selected_items", request, _run)


@app.post("/tools/update_session_state", response_model=SessionResponse)
def update_session_state(request: UpdateSessionStateRequest) -> SessionResponse:
    def _run() -> SessionResponse:
        s = repo.update_session_state(request.session_id, request.state_patch, status=request.status)
        if s is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        return SessionResponse(session_id=s.session_id, case_id=s.case_id, state=s.state_json, status=s.status)

    return run_with_logging("update_session_state", request, _run)


@app.post("/tools/append_chat_message", response_model=dict)
def append_chat_message(request: AppendChatMessageRequest) -> dict:
    def _run() -> BaseModel:
        repo.append_chat_message(request.session_id, request.role, request.content)

        class _Resp(BaseModel):
            ok: bool = True

        return _Resp()

    run_with_logging("append_chat_message", request, _run)
    return {"ok": True}


@app.post("/tools/create_test_order", response_model=CreateTestOrderResponse)
def create_test_order(request: CreateTestOrderRequest) -> CreateTestOrderResponse:
    def _run() -> CreateTestOrderResponse:
        oid = repo.create_test_order(
            customer_email=str(request.customer_email),
            customer_phone_last4=request.customer_phone_last4,
            item_category=request.item_category,
            price=str(request.price),
            shipping_fee=str(request.shipping_fee),
            status=request.status,
            delivery_date=request.delivery_date,
        )
        return CreateTestOrderResponse(order_id=oid)

    return run_with_logging("create_test_order", request, _run)


@app.post("/tools/get_case_status", response_model=GetCaseStatusResponse)
def get_case_status(request: GetCaseStatusRequest) -> GetCaseStatusResponse:
    def _run() -> GetCaseStatusResponse:
        status, eta, tracking = repo.get_case_status(request.case_id)
        return GetCaseStatusResponse(status=status, eta=eta, refund_tracking=tracking)

    return run_with_logging("get_case_status", request, _run)


@app.post("/tools/upload_evidence", response_model=UploadEvidenceResponse)
def upload_evidence(request: UploadEvidenceRequest) -> UploadEvidenceResponse:
    def _run() -> UploadEvidenceResponse:
        evidence_id, stored_path = repo.upload_evidence(
            session_id=request.session_id,
            file_name=request.file_name,
            mime_type=request.mime_type,
            size_bytes=request.size_bytes,
            content_base64=request.content_base64,
        )
        return UploadEvidenceResponse(evidence_id=evidence_id, stored_path=stored_path)

    return run_with_logging("upload_evidence", request, _run)


@app.post("/tools/get_evidence", response_model=GetEvidenceResponse)
def get_evidence(request: GetEvidenceRequest) -> GetEvidenceResponse:
    def _run() -> GetEvidenceResponse:
        rows = repo.get_evidence(request.case_id)
        return GetEvidenceResponse(
            evidence=[
                {
                    "evidence_id": r.evidence_id,
                    "session_id": r.session_id,
                    "case_id": r.case_id,
                    "file_name": r.file_name,
                    "mime_type": r.mime_type,
                    "size_bytes": r.size_bytes,
                    "uploaded_at": r.uploaded_at.isoformat(),
                }
                for r in rows
            ]
        )

    return run_with_logging("get_evidence", request, _run)


@app.post("/tools/validate_evidence", response_model=ValidateEvidenceResponse)
def validate_evidence(request: ValidateEvidenceRequest) -> ValidateEvidenceResponse:
    def _run() -> ValidateEvidenceResponse:
        passed, confidence, reasons, approach = repo.validate_evidence(
            evidence_id=request.evidence_id,
            order_id=request.order_id,
            item_id=request.item_id,
        )
        return ValidateEvidenceResponse(
            passed=passed,
            confidence=confidence,
            reasons=reasons,
            approach=approach,
        )

    return run_with_logging("validate_evidence", request, _run)


@app.post("/tools/get_policy", response_model=GetPolicyResponse)
def get_policy_endpoint(request: GetPolicyRequest) -> GetPolicyResponse:
    return run_with_logging(
        "get_policy",
        request,
        lambda: get_policy(
            item_category=request.item_category,
            reason=request.reason,
            order_date=request.order_date,
            delivery_date=request.delivery_date,
        ),
    )


@app.post("/tools/check_eligibility", response_model=CheckEligibilityResponse)
def check_eligibility_endpoint(request: CheckEligibilityRequest) -> CheckEligibilityResponse:
    return run_with_logging(
        "check_eligibility",
        request,
        lambda: check_eligibility(order=request.order, policy=request.policy, reason=request.reason),
    )


@app.post("/tools/compute_refund", response_model=ComputeRefundResponse)
def compute_refund_endpoint(request: ComputeRefundRequest) -> ComputeRefundResponse:
    return run_with_logging(
        "compute_refund",
        request,
        lambda: compute_refund(order=request.order, policy=request.policy, reason=request.reason),
    )


@app.post("/tools/create_return", response_model=CreateReturnResponse)
def create_return_endpoint(request: CreateReturnRequest) -> CreateReturnResponse:
    def _run() -> CreateReturnResponse:
        rma_id = repo.create_return(order_id=request.order_id, item_id=request.item_id, method=request.method)
        return CreateReturnResponse(rma_id=rma_id)

    return run_with_logging("create_return", request, _run)


@app.post("/tools/create_label", response_model=CreateLabelResponse)
def create_label_endpoint(request: CreateLabelRequest) -> CreateLabelResponse:
    def _run() -> CreateLabelResponse:
        label_id, url = repo.create_label(rma_id=request.rma_id)
        return CreateLabelResponse(label_id=label_id, url=url)

    return run_with_logging("create_label", request, _run)


@app.post("/tools/create_escalation", response_model=CreateEscalationResponse)
def create_escalation_endpoint(request: CreateEscalationRequest) -> CreateEscalationResponse:
    def _run() -> CreateEscalationResponse:
        ticket_id = repo.create_escalation(case_id=request.case_id, reason=request.reason, evidence=request.evidence)
        return CreateEscalationResponse(ticket_id=ticket_id)

    return run_with_logging("create_escalation", request, _run)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception) -> Any:
    if isinstance(exc, HTTPException):
        raise exc
    return JSONResponse(status_code=500, content={"detail": "internal_error"})
