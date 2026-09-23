"""
Pre-loaded Ethiopian material rate database (seed data).
Aligned with MoUDC classification codes.
Run once after migrations: python -m app.modules.rates.seed
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.modules.rates.models import Rate

RATES = [
    # 1100: Excavation & Site Work
    {"item_code": "1101", "description": "Bulk excavation in ordinary soil", "unit": "m³", "rate_per_unit": 350, "rate_source": "MoUDC 2024", "region": "National Average"},
    {"item_code": "1102", "description": "Excavation in hard soil/rock", "unit": "m³", "rate_per_unit": 650, "rate_source": "MoUDC 2024", "region": "National Average"},

    # 2100/2200: Concrete
    {"item_code": "2101", "description": "C-25 Concrete for substructure", "unit": "m³", "rate_per_unit": 4500, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},
    {"item_code": "2201", "description": "C-25 Concrete for superstructure", "unit": "m³", "rate_per_unit": 4700, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},

    # 2411/2412: Reinforcement
    {"item_code": "2411", "description": "Deformed bar Ø8mm and below", "unit": "kg", "rate_per_unit": 48, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},
    {"item_code": "2412", "description": "Deformed bar Ø10mm and above", "unit": "kg", "rate_per_unit": 45, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},

    # 3100: Masonry
    {"item_code": "3101", "description": "200mm thick HCB wall", "unit": "m²", "rate_per_unit": 850, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},

    # 4100/4500: Finishes
    {"item_code": "4101", "description": "Internal plastering with 1:3 cement mortar", "unit": "m²", "rate_per_unit": 180, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},
    {"item_code": "4501", "description": "Plastic emulsion paint to internal walls", "unit": "m²", "rate_per_unit": 95, "rate_source": "Market Survey 2024", "region": "Addis Ababa"},
]

async def seed():
    async with AsyncSessionLocal() as db:
        for r in RATES:
            rate = Rate(**r, project_id=None)
            db.add(rate)
        await db.commit()
    print(f"Seeded {len(RATES)} MoUDC-aligned rates.")

if __name__ == "__main__":
    asyncio.run(seed())
