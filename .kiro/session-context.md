# Digital Mehandis — Session Context

> Read this at the start of every session. Last updated: 2026-09-23

## Identity
- **Digital Mehandis** — standalone, free, open-source (GPL-3.0) QS web platform for the Ethiopian construction community.
- Independent project. OpenConstructionERP (AGPL) is a design reference only — never copy its code.
- Repo: `RandomCreatives/DigitalMehandis_v1.0.0`

## Current plan
`openspec/changes/standalone-restructure/` — step 1 (cleanup) done; step 2 (backend restructure) next.

## Stack
Next.js 14 + Tailwind + Fabric.js + PDF.js | FastAPI + SQLAlchemy 2 async + Alembic | PostgreSQL (prod) / SQLite (dev) | JWT auth | ezdxf for DXF.

## Known debt
- Models split by phase: `db/models.py`, `models_phase2.py`, `models_phase3.py`, `models_cost.py`
- Some tables created by `backend/create_tables.py` instead of Alembic
- Rate files duplicated in `frontend/public/attachments/` (UI fetches them statically)
- Tests cover only auth and BBS

## Run locally
- Backend: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend: `cd frontend && npm run dev`
