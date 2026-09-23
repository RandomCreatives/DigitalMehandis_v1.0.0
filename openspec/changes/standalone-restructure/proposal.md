## Why

Digital Mehandis grew phase by phase (`models_phase2.py`, `models_phase3.py`, tables created outside Alembic, scratch scripts at the root). It works, but the structure makes it hard to maintain, test, and open to community contributors.

The goal is a **standalone web platform for the Ethiopian construction community** (students, QS professionals, consultants, contractors). It is independent of OpenConstructionERP: that project may be used as a *design reference only*; no code is copied (it is AGPL-licensed, which would constrain our licensing and future hosted offering).

## Decisions

- Audience: all community segments (students → contractors)
- Delivery: hosted web app first; offline later if needed
- Interface language: English (Amharic later)
- License: stays GPL-3.0

## What Changes

1. **Cleanup** — remove scratch scripts, single rate-data location (`data/rates/`), honest README.
2. **Backend restructure** — every feature is a self-contained module (`models.py`, `schemas.py`, `service.py`, `router.py`, `tests/`); merge `models*.py` phase files into their modules; one clean Alembic baseline replacing `create_tables.py`.
3. **Ethiopia layer** (`app/ethiopia/`) — ETB currency, 15% VAT, Ethiopian calendar conversion, MoUDC work-section codes, regional rate context.
4. **BOQ upgrade** — hierarchical BOQ (sections → items), markups (overhead, profit, contingency, VAT), draft/locked/approved states.
5. **Rates as data** — rates carry source, region, and effective date; versioned imports from `data/rates/`.
6. **Tests** — end-to-end: drawing → take-off → BOQ → price → export.
7. **Frontend** — mirror module layout (`src/features/*`).

## Non-goals (for now)

BIM/IFC, vector databases, full ERP (procurement, HSE, CRM), multi-country packs.

## Impact

Large internal refactor; user-facing behavior stays the same until steps 3–4. Each step lands as a separate reviewable commit.
