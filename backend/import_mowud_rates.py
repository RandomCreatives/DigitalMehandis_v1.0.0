import asyncio
import os
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.modules.cost_library.models import RateSource, RateItem
from app.modules.cost_library.parser import MoWUDCostParser
from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def import_all():
    parser = MoWUDCostParser()
    attachments_dir = "../data/rates"

    async with AsyncSessionLocal() as db:
        # Create the Source record
        source = RateSource(
            title="MoWUD Direct Cost 2018 3rd Quarter",
            issuing_authority="Addis Ababa City Administration",
            region="Addis Ababa",
            fiscal_year="2018",
            quarter="3",
            calendar_system="GC", # Assuming GC based on 2018, or EC if 2010/2011? User said 2018.
            notes="Automated batch import from 50-page PDF"
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        print(f"Created RateSource: {source.id}")

        all_items = []
        # Pages are named Page 1.pdf to Page 51.pdf
        for i in range(1, 52):
            filename = f"Page {i}.pdf"
            path = os.path.join(attachments_dir, filename)
            if os.path.exists(path):
                print(f"Parsing {filename}...")
                page_items = parser.parse_page(path, 0)
                for item in page_items:
                    item["source_page"] = i
                all_items.extend(page_items)

        print(f"Total items parsed: {len(all_items)}")

        # Insert flat items first to get IDs
        db_items = {}
        for item in all_items:
            # Skip noise like the "2018" header
            if item["item_no"] == "2018" or not item["description"]:
                continue

            ri = RateItem(
                rate_source_id=source.id,
                item_no=item["item_no"],
                description=item["description"],
                unit=item["unit"] or "—",
                direct_cost=item["direct_cost"],
                source_page=item["source_page"],
                confidence=0.9 # High confidence for regex match
            )
            db.add(ri)
            db_items[item["item_no"]] = ri

        await db.flush() # Get IDs without committing

        # Wire up hierarchy
        link_count = 0
        for item_no, ri in db_items.items():
            if "." in item_no:
                parent_no = ".".join(item_no.split(".")[:-1])
                if parent_no in db_items:
                    ri.parent_id = db_items[parent_no].id
                    link_count += 1

        await db.commit()
        print(f"Import complete. Linked {link_count} items in hierarchy.")

if __name__ == "__main__":
    asyncio.run(import_all())
