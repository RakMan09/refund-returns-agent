# Online Deployment Guide (Public Demo)

This guide shows how to host `policyLLM-support-bot` as a public, usable demo.

## Recommended topology
- `tool_server` (FastAPI)
- `agent_server` (FastAPI)
- `ui` (Streamlit)
- Managed `Postgres`

## Recommended default for public demos
- Set `AGENT_MODE=deterministic` first.
- Move to `AGENT_MODE=hybrid` only after model adapters are mounted and verified.

## Option A: Render (recommended for portfolio demos)
1. Push repo to GitHub.
2. In Render, create:
   - one Postgres database
   - one Web Service for `tool_server`
   - one Web Service for `agent_server`
   - one Web Service for `ui`
3. Configure service start commands:
   - Tool server:
     - `uvicorn services.tool_server.app.main:app --host 0.0.0.0 --port $PORT`
   - Agent server:
     - `uvicorn services.agent_server.app.main:app --host 0.0.0.0 --port $PORT`
   - UI:
     - `streamlit run services/ui/app.py --server.address 0.0.0.0 --server.port $PORT`
4. Set environment variables:
   - Tool server:
     - `DATABASE_URL=<managed_postgres_connection_string>`
     - `LOG_LEVEL=INFO`
     - `EVIDENCE_STORAGE_DIR=data/evidence`
     - `APPROACH_B_CATALOG_DIR=data/raw/product_catalog_images`
     - `APPROACH_B_ANOMALY_DIR=data/raw/anomaly_images`
   - Agent server:
     - `TOOL_SERVER_URL=<tool_server_public_url>`
     - `AGENT_MODE=deterministic`
     - `LLM_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2`
     - `LLM_ADAPTER_DIR=models/dpo_qlora/adapter`
     - `LLM_DEVICE=auto`
     - `LLM_DTYPE=auto`
     - `LOG_LEVEL=INFO`
   - UI:
     - `AGENT_SERVER_URL=<agent_server_public_url>`
5. Open the UI service URL and validate:
   - start chat
   - resolve a guided case
   - resume session
   - create test order

## Option B: Railway / Fly.io
Use the same service split and environment variables as Option A.

## Production hardening checklist
- Use managed persistent storage for evidence files.
- Add auth/rate limiting before public launch.
- Restrict CORS origins to your hosted UI domain.
- Store all secrets in platform secret manager only.
- Keep release artifacts and runtime smoke checks in CI.

## Hosted demo section for README
When deployed, add:
- Demo URL
- Current mode (`deterministic`/`hybrid`)
- Known limitations (test-only data, no real payments)
