from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    customer_email: Mapped[str] = mapped_column(String, nullable=False)
    customer_phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    item_category: Mapped[str] = mapped_column(String, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    item_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class ReturnRecord(Base):
    __tablename__ = "returns"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_returns_idempotency"),)

    rma_id: Mapped[str] = mapped_column(String, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LabelRecord(Base):
    __tablename__ = "labels"

    label_id: Mapped[str] = mapped_column(String, primary_key=True)
    rma_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EscalationRecord(Base):
    __tablename__ = "escalations"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_escalations_idempotency"),)

    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ToolCallLog(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EvidenceValidationRecord(Base):
    __tablename__ = "evidence_validations"
    __table_args__ = (
        UniqueConstraint("evidence_id", "order_id", "item_id", name="uq_evidence_validation_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    approach: Mapped[str] = mapped_column(String, nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
