"""
Pricing Engine — computes final unit rates from direct costs using
government-standard overhead, profit, and tax percentages.
"""
from enum import Enum
from dataclasses import dataclass, field


class PricingMode(str, Enum):
    DIRECT_COST_ONLY = "DIRECT_COST_ONLY"
    ADDITIVE = "ADDITIVE"
    COMPOUNDED = "COMPOUNDED"


@dataclass
class PricingSettings:
    overhead_percent: float = 8.0
    profit_percent: float = 10.0
    tax_percent: float = 0.0
    mode: PricingMode = field(default=PricingMode.ADDITIVE)


class PricingEngine:
    """
    Implements Ethiopian government construction pricing rules.

    Overhead and profit percentages follow MoUDC guidelines:
    - Overhead varies by contractor grade
    - Profit varies by estimated project value (ETB)
    """

    # Government defaults by contractor grade
    OVERHEAD_BY_GRADE: dict[str, float] = {
        "GRADE_1": 10.0,
        "GRADE_2": 10.0,
        "GRADE_3": 10.0,
        "GRADE_4": 8.0,
        "GRADE_5": 8.0,
        "GRADE_6": 6.0,
    }

    # Government defaults by estimated project value (ETB)
    # Each tuple: (upper_threshold_inclusive, profit_percent)
    PROFIT_BY_VALUE: list[tuple[float, float]] = [
        (5_000_000, 13.0),
        (15_000_000, 11.0),
        (30_000_000, 10.0),
        (50_000_000, 10.0),
        (float("inf"), 7.0),
    ]

    @staticmethod
    def final_unit_rate(direct_cost: float, settings: PricingSettings) -> float:
        """
        Compute the final unit rate from a direct cost using the given settings.

        Modes:
        - DIRECT_COST_ONLY: no markup applied
        - ADDITIVE:         subtotal = direct_cost × (1 + overhead + profit)
        - COMPOUNDED:       subtotal = direct_cost × (1 + overhead) × (1 + profit)

        Tax is always applied on top of the subtotal.
        """
        overhead = settings.overhead_percent / 100
        profit = settings.profit_percent / 100
        tax = settings.tax_percent / 100

        if settings.mode == PricingMode.DIRECT_COST_ONLY:
            subtotal = direct_cost
        elif settings.mode == PricingMode.ADDITIVE:
            subtotal = direct_cost * (1 + overhead + profit)
        elif settings.mode == PricingMode.COMPOUNDED:
            subtotal = direct_cost * (1 + overhead) * (1 + profit)
        else:
            subtotal = direct_cost

        return round(subtotal * (1 + tax), 2)

    @staticmethod
    def amount(quantity: float, unit_rate: float) -> float:
        """Compute line amount = quantity × unit_rate, rounded to 2 dp."""
        return round(quantity * unit_rate, 2)

    @classmethod
    def suggested_overhead(cls, grade: str) -> float:
        """Return the government-suggested overhead % for a contractor grade."""
        return cls.OVERHEAD_BY_GRADE.get(grade, 8.0)

    @classmethod
    def suggested_profit(cls, estimated_value: float) -> float:
        """Return the government-suggested profit % for an estimated project value."""
        for threshold, profit in cls.PROFIT_BY_VALUE:
            if estimated_value <= threshold:
                return profit
        return 7.0
