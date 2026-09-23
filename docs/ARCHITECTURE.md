# Digital Mehandis Architecture

## System Overview

```
┌─────────────────┐     HTTPS      ┌──────────────────┐
│  Next.js 14     │ ─────────────► │  FastAPI          │
│  (Frontend)     │                │  (Backend)        │
│  Port 3000      │ ◄───────────── │  Port 8000        │
└─────────────────┘   JSON/REST    └────────┬─────────┘
                                            │ SQLAlchemy
                                            ▼
                                   ┌──────────────────┐
                                   │  PostgreSQL 14   │
                                   │  Port 5432       │
                                   └──────────────────┘
```

## Backend Structure

Every feature is a **self-contained module** in `app/modules/<name>/`.

```
backend/app/
├── main.py              # create_app(): CORS, module loader, /health
├── core/
│   ├── config.py        # Pydantic settings (env vars)
│   ├── security.py      # JWT + bcrypt
│   ├── deps.py          # get_current_user dependency
│   ├── module_loader.py # discovers app/modules/*/router.py
│   ├── constants.py     # unit weights, enums
│   ├── files.py         # upload validation & storage
│   └── logging.py
├── db/
│   ├── base.py          # DeclarativeBase
│   ├── types.py         # GUID, JSONType (portable PostgreSQL/SQLite), now_utc
│   ├── registry.py      # imports every module's models.py
│   ├── session.py       # async engine + get_db
│   └── migrations/      # Alembic (single baseline 0001 + future revisions)
└── modules/
    ├── auth/            # users, register/login/refresh
    ├── projects/
    ├── drawings/        # upload, DXF layers/blocks, revisions, mapping templates
    ├── cad/             # library: DXF/PDF extraction, classification, conversion
    ├── calibration/  measurements/  elements/
    ├── takeoff/         # take-off items, suggested & federated quantities
    ├── boq/             # BOQ generation + Excel/PDF exporters
    ├── boq_items/       # traceable BOQ items + quantity sources
    ├── bbs/             # bar bending schedule + calculator
    ├── rates/  cost_library/  rate_matching/   # rates, MoUDC library, pricing
    └── audit/
```

### Module convention

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy models owned by this module (use `GUID`, `JSONType` from `app.db.types`) |
| `schemas.py` | Pydantic request/response models |
| `service.py` / other `*.py` | Business logic — no FastAPI imports |
| `router.py` | `router = APIRouter(...)`; thin HTTP layer, auto-registered under `/api/v1` |
| `__init__.py` | Docstring; optional `EXTRA_ROUTERS = ["other_router"]` |

Rules:
- A new module is picked up automatically; add its `models` import to `app/db/registry.py`.
- Cross-module imports go through the other module's `models`/`service`, never its `router`.
- A router that fails to import **crashes startup** (no silent skipping).
- Schema changes: edit `models.py`, then `alembic revision --autogenerate -m "..."`.
- `tests/test_structure.py` enforces these rules.

### Table ownership

| Module | Tables |
|---|---|
| `audit` | `audit_logs` |
| `auth` | `users` |
| `bbs` | `bbs_bars` |
| `boq` | `boq_outputs` |
| `boq_items` | `boq_item_sources`, `boq_items`, `quantity_sources` |
| `cad` | `block_mappings_v2`, `drawing_revisions`, `dxf_analysis_jobs`, `dxf_blocks`, `dxf_entities`, `dxf_layers`, `layer_mapping_templates`, `layer_mappings_v2`, `quantity_suggestions` |
| `calibration` | `drawing_calibrations` |
| `cost_library` | `rate_items`, `rate_sources`, `raw_rate_import_rows` |
| `drawings` | `drawing_pages`, `drawings` |
| `elements` | `project_elements` |
| `measurements` | `measurements` |
| `projects` | `projects` |
| `rate_matching` | `element_rate_matches`, `project_pricing_settings` |
| `rates` | `rates` |
| `takeoff` | `federated_quantities`, `suggested_quantities`, `takeoff_items` |

## Frontend Structure

```
src/
├── app/             # Next.js App Router pages
│   ├── page.tsx     # Landing page
│   ├── auth/        # Login & Register
│   └── dashboard/
│       ├── page.tsx              # Project list
│       └── [projectId]/
│           ├── page.tsx          # Project overview
│           ├── drawings/         # PDF upload & viewer
│           ├── takeoff/          # Manual take-off sheet
│           ├── boq/              # BOQ generation & export
│           └── bbs/              # BBS entry & cutting list
├── lib/
│   ├── api.ts           # Axios client with JWT interceptors
│   ├── calculations.ts  # Client-side BBS preview math
│   └── utils.ts         # cn(), formatCurrency()
├── store/
│   ├── authStore.ts     # Zustand auth state
│   └── projectStore.ts  # Zustand project state
└── types/index.ts       # Shared TypeScript interfaces
```

## Key Design Decisions

- **Async throughout**: FastAPI + asyncpg + SQLAlchemy async for non-blocking I/O
- **JWT in localStorage**: Phase 1 simplicity; upgrade to httpOnly cookies in Phase 2
- **Client-side BBS preview**: Calculations run in browser for instant feedback, confirmed by backend on save
- **Rate matching**: Simple substring match in Phase 1; upgrade to fuzzy/semantic search in Phase 2
- **PDF serving**: Files served directly from backend with auth check; use CDN/MinIO in Phase 2
