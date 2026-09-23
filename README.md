# Digital Mehandis

**A free, open-source quantity surveying (QS) platform built for the Ethiopian construction community** — students, QS professionals, consultants, and contractors.

Upload drawings → take off quantities → produce a priced Bill of Quantities (BOQ) and Bar Bending Schedule (BBS) in the Ethiopian MoUDC format, using local unit rates in Ethiopian Birr.

> Digital Mehandis is an independent, standalone project. It is not a fork or module of any other ERP.

## What it does today
- PDF drawing upload, scale calibration, and on-screen measurement
- DXF (CAD) import with automatic classification of Ethiopian block/layer names
- Take-off → BOQ with full traceability (every quantity knows its source)
- Bar Bending Schedule with automatic calculations
- Substructure / superstructure separation
- Ethiopian MoUDC unit-rate library, rate matching, and pricing
- Drawing revisions and audit log
- Export to Excel and PDF

## Roadmap
See [`openspec/changes/standalone-restructure/`](openspec/changes/standalone-restructure/proposal.md).
In short: clean modular structure → Ethiopia layer (Birr, 15% VAT, Ethiopian calendar, MoUDC codes) → hierarchical BOQ with markups → tested end-to-end workflow → community rate data.

## Tech stack
- **Frontend**: Next.js 14, Tailwind CSS, Fabric.js, PDF.js, Zustand
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0 (async), Alembic
- **Database**: PostgreSQL (production), SQLite (local development)
- **Auth**: JWT (access + refresh tokens)

## Repository layout
```
backend/      FastAPI app (app/modules = feature modules)
frontend/     Next.js web app
data/rates/   Ethiopian unit-rate source files (CSV/JSON) — single source of truth
config/       Community-editable classification config (e.g. CAD block names)
docs/         Architecture, database, user guide, contributing
openspec/     Planned and completed change proposals
scripts/      Utility scripts (scripts/dev = ad-hoc developer tools)
```

## Quick start

### With Docker
```bash
docker-compose up --build
```

### Manual
**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

API docs: http://localhost:8000/api/docs

## Contributing
Contributions from the community are welcome — especially rate data, CAD block names, and QS domain review. See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## License
GNU GPL v3 — see [LICENSE](LICENSE).
