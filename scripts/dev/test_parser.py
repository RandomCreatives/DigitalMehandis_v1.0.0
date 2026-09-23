from app.utils.cost_parser import MoWUDCostParser
import json

parser = MoWUDCostParser()
# Page 10 (index 9) had the sample data I saw earlier
items = parser.parse_page("data/rates/Page 10.pdf", 0) # The file is only 1 page long since they are separate files

print(f"Found {len(items)} items")
for item in items[:5]:
    print(f"[{item['item_no']}] {item['description'][:60]}... | {item['unit']} | {item['direct_cost']}")

hierarchy = MoWUDCostParser.build_hierarchy(items)
print(f"Roots: {len(hierarchy)}")
