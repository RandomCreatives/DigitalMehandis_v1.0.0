"""
BOQ Generator — matches takeoff items to rates and computes amounts.
"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.takeoff.models import TakeoffItem
from app.modules.rates.models import Rate


class BOQGenerator:
    def __init__(self, db: AsyncSession, project_id: UUID, section: str = "COMBINED"):
        self.db = db
        self.project_id = project_id
        self.section = section

    async def generate(self) -> dict:
        items = await self._get_items()
        rates = await self._get_rates()

        lines = []
        total = 0.0

        for idx, item in enumerate(items, 1):
            rate = self._match_rate(item.description, rates)
            if rate is None:
                continue

            amount = float(item.quantity) * float(rate.rate_per_unit)
            total += amount

            lines.append({
                "item_number": idx,
                "description": item.description,
                "unit": item.unit,
                "quantity": float(item.quantity),
                "rate": float(rate.rate_per_unit),
                "amount": round(amount, 2),
                "notes": item.notes or "",
            })

        return {
            "project_id": self.project_id,
            "section": self.section,
            "lines": lines,
            "total_amount": round(total, 2),
            "currency": "ETB",
        }

    async def _get_items(self) -> list[TakeoffItem]:
        stmt = select(TakeoffItem).where(TakeoffItem.project_id == self.project_id)
        if self.section != "COMBINED":
            stmt = stmt.where(TakeoffItem.section == self.section)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _get_rates(self) -> list[Rate]:
        # Project-specific rates first, then global rates (project_id IS NULL)
        stmt = select(Rate).where(
            (Rate.project_id == self.project_id) | (Rate.project_id.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _match_rate(description: str, rates: list[Rate]) -> Rate | None:
        desc_lower = description.lower()
        for rate in rates:
            if rate.description.lower() in desc_lower or desc_lower in rate.description.lower():
                return rate
        return None
