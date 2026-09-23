## 1. Cleanup
- [x] 1.1 Remove one-off fix scripts and scratch files
- [x] 1.2 Move ad-hoc dev scripts to `scripts/dev/`
- [x] 1.3 Single rate-data location `data/rates/` (frontend/public copy is served for the UI; to be replaced by an API)
- [x] 1.4 Rewrite README with standalone identity
- [x] 1.5 Refresh `.kiro/session-context.md`

## 2. Backend restructure
- [x] 2.1 Define module layout convention in docs/ARCHITECTURE.md
- [x] 2.2 Move models from `db/models*.py` into their feature modules
- [x] 2.3 Split module `__init__.py` into router.py + schemas.py + logic files (deeper router→service extraction continues per module)
- [x] 2.4 Single Alembic baseline; retire `create_tables.py`
- [x] 2.5 Verify on SQLite and PostgreSQL

## 3. Ethiopia layer
- [ ] 3.1 ETB currency + number formatting
- [ ] 3.2 VAT (15%) and tax settings
- [ ] 3.3 Ethiopian ↔ Gregorian calendar conversion
- [ ] 3.4 MoUDC work-section codes as data

## 4. BOQ upgrade
- [ ] 4.1 Hierarchical sections/items
- [ ] 4.2 Markups (overhead, profit, contingency, VAT)
- [ ] 4.3 Draft / locked / approved states

## 5. Rates as data
- [ ] 5.1 Source, region, effective date on rates
- [ ] 5.2 Versioned importer from `data/rates/`; serve rates via API instead of static files

## 6. Tests
- [x] 6.0 CI fixed; runs on SQLite + PostgreSQL + frontend type-check
- [ ] 6.1 End-to-end: take-off → BOQ → pricing → export
- [x] 6.2 CI on PostgreSQL

## 7. Frontend
- [ ] 7.1 `src/features/*` layout mirroring backend modules
