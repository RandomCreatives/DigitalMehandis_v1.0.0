# Alembic migration versions

- `0001_baseline_schema.py` — full schema for every table in `app/modules/*/models.py`.
  It replaces the old phase-by-phase chain, which could not build an empty database.
- New changes: edit a module's `models.py`, then run
  `alembic revision --autogenerate -m "short description"` and review the file.
- The same migrations run on PostgreSQL (production) and SQLite (local dev).

**Existing databases created with the old chain or `create_tables.py`:** back up
first, then either recreate (`alembic downgrade base && alembic upgrade head`)
or, if the schema already matches, run `alembic stamp 0001`.
