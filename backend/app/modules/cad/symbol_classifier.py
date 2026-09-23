"""
Symbol Classifier — classifies DXF block names into construction element categories.
Uses a YAML config file (config/ethiopian_blocks.yaml) that is community-editable.
Phase 2: migrate to DB-backed versioned system.
"""
from pathlib import Path
from typing import Optional
import yaml


# Resolve config path relative to repo root (works inside Docker too)
_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "ethiopian_blocks.yaml"


class SymbolClassifier:
    _data: dict | None = None
    _cache: dict[str, str] = {}

    @classmethod
    def _load(cls) -> None:
        if cls._data is not None:
            return
        path = _CONFIG_PATH
        if not path.exists():
            # Fallback: look relative to CWD (useful in tests)
            path = Path("config/ethiopian_blocks.yaml")
        if not path.exists():
            cls._data = {"categories": {}, "discipline_map": {}}
            return
        with open(path, "r", encoding="utf-8") as f:
            cls._data = yaml.safe_load(f)

    @classmethod
    def classify_block(cls, block_name: str) -> str:
        """
        Classify a block name into a category (e.g. DOOR, WINDOW, TOILET).
        Returns "UNKNOWN" if no pattern matches.
        """
        if not block_name:
            return "UNKNOWN"

        key = block_name.lower().strip()
        if key in cls._cache:
            return cls._cache[key]

        cls._load()
        for category, patterns in cls._data.get("categories", {}).items():
            for pattern in patterns:
                if pattern.lower() in key:
                    cls._cache[key] = category
                    return category

        cls._cache[key] = "UNKNOWN"
        return "UNKNOWN"

    @classmethod
    def get_discipline(cls, category: str) -> str:
        """Return the discipline for a given category (e.g. DOOR → ARCHITECTURAL)."""
        cls._load()
        return cls._data.get("discipline_map", {}).get(category, "UNKNOWN")

    @classmethod
    def classify_with_discipline(cls, block_name: str) -> tuple[str, str]:
        """Returns (category, discipline) tuple."""
        category = cls.classify_block(block_name)
        discipline = cls.get_discipline(category)
        return category, discipline

    @classmethod
    def get_quantities_by_discipline(cls, block_counts: dict[str, int]) -> dict[str, dict[str, int]]:
        """
        Aggregate block counts by discipline.

        Input:  {"DR-01": 5, "WD-02": 10, "WC": 4, "LIGHT-LED": 20}
        Output: {
            "ARCHITECTURAL": {"DOOR": 5, "WINDOW": 10},
            "SANITARY":      {"TOILET": 4},
            "ELECTRICAL":    {"LIGHT_FIXTURE": 20}
        }
        """
        result: dict[str, dict[str, int]] = {}
        for block_name, count in block_counts.items():
            category, discipline = cls.classify_with_discipline(block_name)
            if category == "UNKNOWN" or discipline == "UNKNOWN":
                continue
            result.setdefault(discipline, {})
            result[discipline][category] = result[discipline].get(category, 0) + count
        return result

    @classmethod
    def refresh(cls) -> None:
        """Clear caches (call after updating the YAML file)."""
        cls._data = None
        cls._cache = {}
