# PostgreSQL Setup Guide

Switch from SQLite (local dev) to PostgreSQL for full Phase 2 + Phase 3 support.

---

## 1. Install PostgreSQL 16

Download from: https://www.postgresql.org/download/windows/

During installation:
- Password: `ethioqs_secret` (or your own — update `.env` to match)
- Port: `5432` (default)
- Leave everything else default

---

## 2. Create the database

Open **SQL Shell (psql)** from the Start menu, or use **pgAdmin**.

```sql
CREATE DATABASE ethioqs;
CREATE USER ethioqs WITH PASSWORD 'ethioqs_secret';
GRANT ALL PRIVILEGES ON DATABASE ethioqs TO ethioqs;
-- PostgreSQL 15+ also needs this:
\c ethioqs
GRANT ALL ON SCHEMA public TO ethioqs;
```

---

## 3. Update backend/.env

```env
DATABASE_URL=postgresql+asyncpg://ethioqs:ethioqs_secret@localhost:5432/ethioqs
```

---

## 4. Run migrations

```powershell
cd backend
.\venv\Scripts\alembic upgrade head
```

This runs both migrations:
- `0001` — Phase 1 tables (users, projects, drawings, etc.)
- `0002` — Phase 2 tables (calibrations, measurements, elements, BOQ items, audit logs)

---

## 5. Seed the rate database

```powershell
.\venv\Scripts\python.exe -c "
import asyncio
from app.modules.rates.seed import seed_rates
from app.db.session import AsyncSessionLocal
async def main():
    async with AsyncSessionLocal() as db:
        await seed_rates(db)
        await db.commit()
        print('Rates seeded.')
asyncio.run(main())
"
```

---

## 6. Restart the backend

```powershell
.\venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Switching back to SQLite (local dev)

```env
DATABASE_URL=sqlite+aiosqlite:///./ethioqs.db
```

Then run: `alembic upgrade head` (the same migrations work on SQLite and PostgreSQL).

---

## Troubleshooting

| Error | Fix |
|---|---|
| `connection refused` | PostgreSQL service not running — start it from Services or pgAdmin |
| `password authentication failed` | Check `.env` password matches what you set during install |
| `database does not exist` | Run the CREATE DATABASE step again |
| `permission denied for schema public` | Run `GRANT ALL ON SCHEMA public TO ethioqs;` inside the `ethioqs` database |
| `alembic: table already exists` | Run `alembic stamp head` then `alembic upgrade head` |
