# Digital Mehandis — Session Context

> Read this at the start of every session. Last updated: 2026-09-23

## Identity
- **Digital Mehandis** — standalone, free, open-source (GPL-3.0) QS web platform for the Ethiopian construction community.
- Independent project. OpenConstructionERP (AGPL) is a design reference only — never copy its code.
- Repo: `RandomCreatives/DigitalMehandis_v1.0.0`

## Current plan
`openspec/changes/standalone-restructure/` — steps 1–2 done (cleanup, backend modules + single migration baseline). Next: step 3 Ethiopia layer (#16).

## Stack
Next.js 14 + Tailwind + Fabric.js + PDF.js | FastAPI + SQLAlchemy 2 async + Alembic | PostgreSQL (prod) / SQLite (dev) | JWT auth | ezdxf for DXF.

## Backend layout
Each feature = `backend/app/modules/<name>/` with models.py / schemas.py / service files / router.py.
See docs/ARCHITECTURE.md. Single Alembic baseline `0001`. Tests: `pytest` (SQLite or PostgreSQL via DATABASE_URL).

## Known debt
- Duplicate routes (same path in two modules): rates CRUD in `boq` + `rates`, bbs sync-to-boq in `bbs` + `rates`
- Rate files duplicated in `frontend/public/attachments/` (UI fetches them statically) — issue #18
- Test coverage still thin on take-off → BOQ → pricing — issue #19

## Run locally
- Backend: `cd backend && alembic upgrade head && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend: `cd frontend && npm run dev`
