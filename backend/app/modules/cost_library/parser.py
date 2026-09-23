import re
import pdfplumber
from typing import List, Dict, Any, Optional
from loguru import logger

class MoWUDCostParser:
    """
    Parses MoWUD (Ministry of Works and Urban Development) hierarchical cost data from PDFs.
    Handles nested items (e.g. 2.7 -> 2.7.1) and multi-line descriptions.
    """

    # Common units found in MoWUD docs (often OCR'd poorly)
    UNIT_MAP = {
        "m3": ["m3", "m'", "ቪ", "ጡ", "፲", "7"],
        "m2": ["m2", "m²", "መ", "ረ"],
        "m": ["m", "ml", "ሊ", "ሜ"],
        "kg": ["kg", "ኪ", "ግ"],
        "pcs": ["pcs", "ቁ", "ጥር"],
        "ls": ["ls", "ጠ", "ቅላ"],
    }

    def __init__(self):
        self.item_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s*(.*)')
        # Matches numbers like 1,658.69 or 975.65 at the end of a string
        self.cost_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*\.\d{2})$')

    def parse_page(self, pdf_path: str, page_number: int) -> List[Dict[str, Any]]:
        items = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_number >= len(pdf.pages):
                    return []

                page = pdf.pages[page_number]
                text = page.extract_text()
                if not text:
                    return []

                lines = text.split('\n')
                current_item = None

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Try to match an item number at the start
                    match = self.item_pattern.match(line)
                    if match:
                        # If we have a pending item, save it
                        if current_item:
                            items.append(current_item)

                        item_no = match.group(1)
                        remainder = match.group(2).strip()

                        # Check if this line has a cost at the end
                        cost_match = self.cost_pattern.search(remainder)
                        if cost_match:
                            cost_str = cost_match.group(1)
                            cost_val = float(cost_str.replace(',', ''))
                            # Remove cost and trailing pipes/chars from description
                            desc_raw = remainder[:remainder.rfind(cost_str)].strip()

                            # Try to extract unit (it's usually just before the cost)
                            # Looking at sample: "2.7.1 | not exceedingl.50m 7 1,658.69"
                            # remainder is "| not exceedingl.50m 7 1,658.69"
                            # desc_raw is "| not exceedingl.50m 7"

                            unit = "UNKNOWN"
                            parts = desc_raw.split()
                            if parts:
                                last_word = parts[-1]
                                for u, aliases in self.UNIT_MAP.items():
                                    if last_word.lower() in aliases:
                                        unit = u
                                        desc_raw = " ".join(parts[:-1])
                                        break

                            current_item = {
                                "item_no": item_no,
                                "description": desc_raw.strip('| ').strip(),
                                "unit": unit,
                                "direct_cost": cost_val,
                                "page": page_number + 1,
                                "is_category": False
                            }
                        else:
                            # It's a category/header line
                            current_item = {
                                "item_no": item_no,
                                "description": remainder.strip('| ').strip(),
                                "unit": None,
                                "direct_cost": 0.0,
                                "page": page_number + 1,
                                "is_category": True
                            }
                    elif current_item:
                        # Append to current item's description if no new item number
                        # But watch out for footer/header noise
                        if not any(noise in line.lower() for noise in ["quarter", "it.no", "page", "total"]):
                             current_item["description"] += " " + line.strip('| ').strip()

                if current_item:
                    items.append(current_item)

        except Exception as e:
            logger.error(f"Error parsing page {page_number} of {pdf_path}: {e}")

        return items

    def parse_multiple_pages(self, pdf_path: str, start_page: int, end_page: int) -> List[Dict[str, Any]]:
        all_items = []
        for p in range(start_page, end_page + 1):
            all_items.extend(self.parse_page(pdf_path, p))
        return all_items

    @staticmethod
    def build_hierarchy(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Organizes flat items into a tree structure based on item_no.
        """
        item_map = {item["item_no"]: item for item in items}
        root_items = []

        for item in items:
            item["children"] = []
            item_no = item["item_no"]
            if "." in item_no:
                parent_no = ".".join(item_no.split(".")[:-1])
                if parent_no in item_map:
                    item_map[parent_no]["children"].append(item)
                else:
                    root_items.append(item)
            else:
                root_items.append(item)

        return root_items
