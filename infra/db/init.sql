CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT NOT NULL,
  customer_email TEXT NOT NULL,
  customer_phone_last4 TEXT NOT NULL,
  item_id TEXT NOT NULL,
  item_category TEXT NOT NULL,
  order_date DATE NOT NULL,
  delivery_date DATE,
  item_price NUMERIC(10,2) NOT NULL,
  shipping_fee NUMERIC(10,2) NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS returns (
  rma_id TEXT PRIMARY KEY,
  idempotency_key TEXT UNIQUE NOT NULL,
  order_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  method TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS labels (
  label_id TEXT PRIMARY KEY,
  rma_id TEXT UNIQUE NOT NULL,
  label_url TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS escalations (
  ticket_id TEXT PRIMARY KEY,
  idempotency_key TEXT UNIQUE NOT NULL,
  case_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  evidence JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
  session_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  state_json JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tool_call_logs (
  id BIGSERIAL PRIMARY KEY,
  tool_name TEXT NOT NULL,
  request_payload JSONB NOT NULL,
  response_payload JSONB,
  error_message TEXT,
  latency_ms INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_records (
  evidence_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  storage_path TEXT NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_validations (
  id BIGSERIAL PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  passed BOOLEAN NOT NULL,
  confidence NUMERIC(4,3) NOT NULL,
  reasons JSONB NOT NULL,
  approach TEXT NOT NULL,
  validated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (evidence_id, order_id, item_id)
);

INSERT INTO orders (
  order_id, merchant_id, customer_email, customer_phone_last4,
  item_id, item_category, order_date, delivery_date,
  item_price, shipping_fee, status
)
VALUES
  ('ORD-1001', 'M-001', 'alice@example.com', '1234', 'ITEM-1', 'electronics', '2025-12-01', '2025-12-05', 120.00, 10.00, 'delivered'),
  ('ORD-1002', 'M-001', 'bob@example.com', '5678', 'ITEM-2', 'fashion', '2025-11-10', '2025-11-14', 55.00, 5.00, 'delivered')
ON CONFLICT (order_id) DO NOTHING;
