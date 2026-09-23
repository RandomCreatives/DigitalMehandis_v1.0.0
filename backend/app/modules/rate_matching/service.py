"""
Rate Matching Service — fuzzy matching between project elements and
government rate library items using unit normalization, category keywords,
and text similarity.
"""
import re
from difflib import SequenceMatcher


class UnitNormalizer:
    """
    Normalizes raw unit strings to canonical forms.
    Returns (normalized_unit, needs_review) where needs_review=True
    means the unit could not be confidently mapped.
    """

    ALIASES: dict[str, list[str]] = {
        "m2": ["m²", "m2", "m?", "sq.m", "sqm"],
        "m3": ["m³", "m3", "cu.m", "cum"],
        "m": ["ml", "m.l", "lin.m", "lm"],
        "pcs": ["pcs", "PCS", "No", "NO", "no.", "nr", "NR", "each"],
        "kg": ["Kg", "KG", "kg"],
        "tonne": ["ton", "Ton", "MT", "mt"],
        "set": ["set", "Set", "SET"],
        "lump sum": ["ls", "LS", "l.s", "lump sum"],
    }
    _reverse: dict[str, str] = {}

    @classmethod
    def _build_reverse(cls) -> None:
        if not cls._reverse:
            for normalized, aliases in cls.ALIASES.items():
                for alias in aliases:
                    cls._reverse[alias.lower()] = normalized

    @classmethod
    def normalize(cls, raw_unit: str) -> tuple[str, bool]:
        """
        Returns (normalized_unit, needs_review).
        needs_review=False means a confident mapping was found.
        """
        cls._build_reverse()
        cleaned = raw_unit.strip()
        normalized = cls._reverse.get(cleaned.lower())
        if normalized:
            return normalized, False
        # Try partial match
        for alias, norm in cls._reverse.items():
            if alias in cleaned.lower():
                return norm, False
        return cleaned, True  # needs review


class RateMatchingService:
    """
    Computes match confidence between a project element and a rate item
    using three signals:
    1. Unit match (binary, 0 or 1)
    2. Category keyword match (0–1)
    3. Text similarity (0–1)
    """

    CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "WALL": ["wall", "block", "masonry", "hcb", "brick"],
        "COLUMN": ["column", "col", "pillar"],
        "BEAM": ["beam", "lintel"],
        "SLAB": ["slab", "floor", "suspended"],
        "FOOTING": ["footing", "foundation", "pad", "strip"],
        "EXCAVATION": ["excavat", "earthwork", "cut", "fill", "backfill"],
        "CONCRETE": ["concrete", "c-25", "c-20", "c-30", "c25", "c20", "c30", "grade"],
        "REBAR": ["rebar", "re-bar", "reinforcement", "bar", "dia", "ø", "grade 75"],
        "FORMWORK": ["formwork", "shuttering", "form work"],
        "PLASTER": ["plaster", "render", "cement sand"],
        "PAINT": ["paint", "emulsion", "primer"],
        "TILE": ["tile", "ceramic", "terrazzo", "marble"],
        "DOOR": ["door", "d/w"],
        "WINDOW": ["window", "w/w"],
        "PIPE": ["pipe", "pvc", "gi", "hdpe"],
        "ROOFING": ["roof", "ega", "corrugated", "truss"],
    }

    @classmethod
    def text_similarity(cls, a: str, b: str) -> float:
        """Compute SequenceMatcher ratio between two strings (case-insensitive)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @classmethod
    def category_match(cls, element_category: str, rate_description: str) -> float:
        """
        Score how well a rate description matches an element category
        based on keyword presence. Returns 0–1.
        """
        keywords = cls.CATEGORY_KEYWORDS.get(element_category.upper(), [])
        if not keywords:
            return 0.0
        desc_lower = rate_description.lower()
        matches = sum(1 for kw in keywords if kw in desc_lower)
        return min(matches / max(len(keywords), 1), 1.0)

    @classmethod
    def unit_match(cls, element_unit: str, rate_unit: str) -> float:
        """Returns 1.0 if normalized units match, 0.0 otherwise."""
        eu, _ = UnitNormalizer.normalize(element_unit)
        ru, _ = UnitNormalizer.normalize(rate_unit)
        return 1.0 if eu == ru else 0.0

    @classmethod
    def compute_confidence(
        cls,
        element_category: str,
        element_description: str,
        element_unit: str,
        rate_description: str,
        rate_unit: str,
        rate_category: str | None = None,
    ) -> tuple[float, str]:
        """
        Compute overall match confidence and a human-readable reason.

        Returns (confidence: float 0–1, reason: str).
        Returns (0.0, "Unit mismatch") immediately if units don't match.

        Weights:
        - unit:     0.3 (binary gate — 0 means no match)
        - category: 0.4
        - text:     0.3
        """
        unit_score = cls.unit_match(element_unit, rate_unit)
        if unit_score == 0:
            return 0.0, "Unit mismatch"

        cat_score = cls.category_match(element_category, rate_description)
        text_score = cls.text_similarity(element_description, rate_description)

        confidence = (unit_score * 0.3) + (cat_score * 0.4) + (text_score * 0.3)

        if confidence >= 0.85:
            reason = "Strong match: unit + category + description"
        elif confidence >= 0.60:
            reason = "Partial match: needs review"
        else:
            reason = "Weak match: low similarity"

        return round(confidence, 3), reason

    @classmethod
    def find_best_matches(
        cls,
        element_category: str,
        element_description: str,
        element_unit: str,
        rate_items: list,
        top_n: int = 5,
    ) -> list[dict]:
        """
        Find the top N rate items that best match a project element.

        Each result dict contains:
        - rate_item_id, description, unit, direct_cost, confidence, reason
        """
        results = []
        for rate in rate_items:
            conf, reason = cls.compute_confidence(
                element_category,
                element_description,
                element_unit,
                rate.description,
                rate.unit,
                rate.work_category,
            )
            if conf > 0:
                results.append(
                    {
                        "rate_item_id": str(rate.id),
                        "description": rate.description,
                        "unit": rate.unit,
                        "direct_cost": rate.direct_cost,
                        "confidence": conf,
                        "reason": reason,
                    }
                )
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:top_n]
