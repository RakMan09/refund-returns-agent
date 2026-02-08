import base64
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from services.tool_server.app.models import (
    Base,
    ChatMessage,
    ChatSession,
    EvidenceRecord,
    EvidenceValidationRecord,
    EscalationRecord,
    LabelRecord,
    Order,
    ReturnRecord,
    ToolCallLog,
)


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Repository:
    def __init__(
        self,
        database_url: str,
        evidence_storage_dir: str = "data/evidence",
        approach_b_catalog_dir: str = "data/raw/product_catalog_images",
        approach_b_anomaly_dir: str = "data/raw/anomaly_images",
    ):
        self.engine = create_engine(database_url, future=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.evidence_storage_dir = Path(evidence_storage_dir)
        self.approach_b_catalog_dir = Path(approach_b_catalog_dir)
        self.approach_b_anomaly_dir = Path(approach_b_anomaly_dir)
        self.evidence_storage_dir.mkdir(parents=True, exist_ok=True)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)
        self._seed_orders_if_empty()

    def _seed_orders_if_empty(self) -> None:
        with self.session_factory() as session:
            existing = session.scalar(select(Order.order_id).limit(1))
            if existing:
                return
            session.add_all(
                [
                    Order(
                        order_id="ORD-1001",
                        merchant_id="M-001",
                        customer_email="alice@example.com",
                        customer_phone_last4="1234",
                        item_id="ITEM-1",
                        item_category="electronics",
                        order_date=datetime(2025, 12, 1).date(),
                        delivery_date=datetime(2025, 12, 5).date(),
                        item_price="120.00",
                        shipping_fee="10.00",
                        status="delivered",
                    ),
                    Order(
                        order_id="ORD-1002",
                        merchant_id="M-001",
                        customer_email="bob@example.com",
                        customer_phone_last4="5678",
                        item_id="ITEM-2",
                        item_category="fashion",
                        order_date=datetime(2025, 11, 10).date(),
                        delivery_date=datetime(2025, 11, 14).date(),
                        item_price="55.00",
                        shipping_fee="5.00",
                        status="delivered",
                    ),
                ]
            )
            session.commit()

    def lookup_order(self, *, order_id: str | None, email: str | None, phone_last4: str | None) -> Order | None:
        with self.session_factory() as session:
            query = select(Order)
            if order_id is not None:
                query = query.where(Order.order_id == order_id)
            elif email is not None:
                query = query.where(Order.customer_email == email)
            else:
                query = query.where(Order.customer_phone_last4 == phone_last4)
            return session.scalar(query.limit(1))

    def list_orders(self, customer_identifier: str) -> list[Order]:
        with self.session_factory() as session:
            if customer_identifier.upper().startswith("ORD-"):
                q = select(Order).where(Order.order_id == customer_identifier)
            elif "@" in customer_identifier:
                q = select(Order).where(Order.customer_email == customer_identifier)
            else:
                q = select(Order).where(Order.customer_phone_last4 == customer_identifier)
            return list(session.scalars(q.limit(50)).all())

    def list_order_items(self, order_id: str) -> list[Order]:
        with self.session_factory() as session:
            q = select(Order).where(Order.order_id == order_id)
            return list(session.scalars(q.limit(50)).all())

    def create_session(self, session_id: str, case_id: str, state: dict, status: str) -> ChatSession:
        with self.session_factory() as session:
            existing = session.get(ChatSession, session_id)
            if existing:
                return existing
            now = _utcnow_naive()
            row = ChatSession(
                session_id=session_id,
                case_id=case_id,
                state_json=state,
                status=status,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return row

    def get_session(self, session_id: str) -> ChatSession | None:
        with self.session_factory() as session:
            return session.get(ChatSession, session_id)

    def update_session_state(self, session_id: str, state_patch: dict, status: str | None = None) -> ChatSession | None:
        with self.session_factory() as session:
            row = session.get(ChatSession, session_id)
            if row is None:
                return None
            merged = dict(row.state_json or {})
            merged.update(state_patch)
            row.state_json = merged
            if status is not None:
                row.status = status
            row.updated_at = _utcnow_naive()
            session.commit()
            session.refresh(row)
            return row

    def append_chat_message(self, session_id: str, role: str, content: str) -> None:
        with self.session_factory() as session:
            row = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                created_at=_utcnow_naive(),
            )
            session.add(row)
            session.commit()

    def create_return(self, order_id: str, item_id: str, method: str) -> str:
        key = f"{order_id}:{item_id}:{method}"
        with self.session_factory() as session:
            existing = session.scalar(select(ReturnRecord).where(ReturnRecord.idempotency_key == key).limit(1))
            if existing:
                return existing.rma_id

            digest = sha256(key.encode("utf-8")).hexdigest()[:12]
            rma_id = f"RMA-{digest.upper()}"
            record = ReturnRecord(
                rma_id=rma_id,
                idempotency_key=key,
                order_id=order_id,
                item_id=item_id,
                method=method,
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            return rma_id

    def create_label(self, rma_id: str) -> tuple[str, str]:
        with self.session_factory() as session:
            existing = session.scalar(select(LabelRecord).where(LabelRecord.rma_id == rma_id).limit(1))
            if existing:
                return existing.label_id, existing.label_url

            digest = sha256(rma_id.encode("utf-8")).hexdigest()[:12]
            label_id = f"LBL-{digest.upper()}"
            url = f"https://labels.local/{label_id}.pdf"
            record = LabelRecord(
                label_id=label_id,
                rma_id=rma_id,
                label_url=url,
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            return label_id, url

    def create_escalation(self, case_id: str, reason: str, evidence: dict) -> str:
        key = f"{case_id}:{reason}"
        with self.session_factory() as session:
            existing = session.scalar(
                select(EscalationRecord).where(EscalationRecord.idempotency_key == key).limit(1)
            )
            if existing:
                return existing.ticket_id

            digest = sha256(key.encode("utf-8")).hexdigest()[:12]
            ticket_id = f"ESC-{digest.upper()}"
            record = EscalationRecord(
                ticket_id=ticket_id,
                idempotency_key=key,
                case_id=case_id,
                reason=reason,
                evidence=evidence,
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            return ticket_id

    def create_test_order(
        self,
        *,
        customer_email: str,
        customer_phone_last4: str,
        item_category: str,
        price: str,
        shipping_fee: str,
        status: str,
        delivery_date,
    ) -> str:
        order_id = f"ORD-{uuid4().hex[:10].upper()}"
        item_id = f"ITEM-{uuid4().hex[:8].upper()}"
        merchant_id = "M-TEST"
        with self.session_factory() as session:
            row = Order(
                order_id=order_id,
                merchant_id=merchant_id,
                customer_email=customer_email,
                customer_phone_last4=customer_phone_last4,
                item_id=item_id,
                item_category=item_category,
                order_date=_utcnow_naive().date(),
                delivery_date=delivery_date,
                item_price=price,
                shipping_fee=shipping_fee,
                status=status,
            )
            session.add(row)
            session.commit()
        return order_id

    def get_case_status(self, case_id: str) -> tuple[str, str | None, str | None]:
        with self.session_factory() as session:
            s = session.scalar(select(ChatSession).where(ChatSession.case_id == case_id).limit(1))
            if s is None:
                return "not_found", None, None
            if s.status in {"resolved", "pending_refund", "pending_return"}:
                return s.status, "2-5 business days", f"TRACK-{case_id[-6:].upper()}"
            return s.status, None, None

    def upload_evidence(
        self,
        *,
        session_id: str,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        content_base64: str,
    ) -> tuple[str, str]:
        with self.session_factory() as session:
            chat_session = session.get(ChatSession, session_id)
            if chat_session is None:
                raise ValueError("session_not_found")
            file_bytes = base64.b64decode(content_base64, validate=True)
            if len(file_bytes) != size_bytes:
                raise ValueError("evidence_size_mismatch")
            ext = Path(file_name).suffix or ".bin"
            evidence_id = f"EVD-{uuid4().hex[:12].upper()}"
            case_dir = self.evidence_storage_dir / chat_session.case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            store_path = case_dir / f"{evidence_id}{ext}"
            store_path.write_bytes(file_bytes)
            row = EvidenceRecord(
                evidence_id=evidence_id,
                session_id=session_id,
                case_id=chat_session.case_id,
                file_name=file_name,
                mime_type=mime_type,
                size_bytes=size_bytes,
                storage_path=str(store_path),
                uploaded_at=_utcnow_naive(),
            )
            session.add(row)
            session.commit()
            return evidence_id, str(store_path)

    def get_evidence(self, case_id: str) -> list[EvidenceRecord]:
        with self.session_factory() as session:
            q = select(EvidenceRecord).where(EvidenceRecord.case_id == case_id)
            q = q.order_by(EvidenceRecord.uploaded_at.desc())
            return list(session.scalars(q.limit(20)).all())

    def validate_evidence(
        self, *, evidence_id: str, order_id: str, item_id: str
    ) -> tuple[bool, Decimal, list[str], str]:
        with self.session_factory() as session:
            existing = session.scalar(
                select(EvidenceValidationRecord)
                .where(EvidenceValidationRecord.evidence_id == evidence_id)
                .where(EvidenceValidationRecord.order_id == order_id)
                .where(EvidenceValidationRecord.item_id == item_id)
                .limit(1)
            )
            if existing:
                return (
                    bool(existing.passed),
                    Decimal(existing.confidence),
                    list(existing.reasons),
                    existing.approach,
                )

            evd = session.get(EvidenceRecord, evidence_id)
            if evd is None:
                raise ValueError("evidence_not_found")
            score = Decimal("0.10")
            reasons: list[str] = []
            file_name = evd.file_name.lower()
            if evd.mime_type.startswith("image/"):
                score += Decimal("0.30")
                reasons.append("Image MIME type accepted")
            if evd.size_bytes >= 15_000:
                score += Decimal("0.25")
                reasons.append("File size suggests non-empty evidence")
            if any(k in file_name for k in ["damage", "broken", "crack", "defect", "leak"]):
                score += Decimal("0.25")
                reasons.append("Filename indicates defect context")
            if self.approach_b_catalog_dir.exists() and self.approach_b_anomaly_dir.exists():
                score += Decimal("0.10")
                reasons.append("Approach B reference directories detected")
            if not reasons:
                reasons.append("Evidence quality too low for validation")
            confidence = min(Decimal("0.99"), score.quantize(Decimal("0.001")))
            passed = confidence >= Decimal("0.600")
            if passed:
                reasons.append("Evidence considered sufficient for policy requirement")

            row = EvidenceValidationRecord(
                evidence_id=evidence_id,
                order_id=order_id,
                item_id=item_id,
                passed=passed,
                confidence=confidence,
                reasons=reasons,
                approach="approach_b_simulation",
                validated_at=_utcnow_naive(),
            )
            session.add(row)
            session.commit()
            return passed, confidence, reasons, "approach_b_simulation"

    def log_tool_call(
        self,
        *,
        tool_name: str,
        request_payload: dict,
        response_payload: dict | None,
        error_message: str | None,
        latency_ms: int,
    ) -> None:
        with self.session_factory() as session:
            log = ToolCallLog(
                tool_name=tool_name,
                request_payload=request_payload,
                response_payload=response_payload,
                error_message=error_message,
                latency_ms=latency_ms,
                created_at=_utcnow_naive(),
            )
            session.add(log)
            session.commit()


def mask_email(email: str) -> str:
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        local_masked = local[0] + "*"
    else:
        local_masked = local[:2] + "*" * (len(local) - 2)
    return f"{local_masked}@{domain}"
