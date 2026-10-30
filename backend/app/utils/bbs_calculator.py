"""
BBS cutting length, weight, and lap calculator.

Codes of practice (corrected)
-----------------------------
Bar bending schedules in Ethiopian practice are commonly quoted as
"per EBCS 3". **EBCS-3 is Design of Steel Structures** -- it has nothing to do
with reinforced-concrete bar schedules. The EBCS-1995 series is:

    EBCS-1  Basis of design / actions
    EBCS-2  Structural use of concrete      <-- the one a BBS should cite
    EBCS-3  Design of steel structures      <-- NOT this
    EBCS-4  Composite structures
    EBCS-5  Timber
    EBCS-6  Masonry
    EBCS-7  Foundations
    EBCS-8  Earthquake

Correct citations for a bar bending schedule are:

* **ES EN 1992-1-1:2015 (EC2) §8.4** -- anchorage ``l_bd`` and laps
  ``l_0 = a1*a2*a3*a5*a6 * l_b,rqd``, with ``a6 = 1.5`` (100 % lapped) or
  ``1.4`` (staggered).
* **BS 8666** -- shape codes and bend deductions (mandrel diameter 4*phi for
  phi <= 16 mm, 7*phi above). BS 8666 does **not** define lap lengths; asking
  this module for a BS 8666 lap raises instead of inventing one.

ES EN 1992-1-1:2015 superseded and withdrew EBCS-2:1995, but site practice
still says "EBCS". Both are therefore supported, and every result carries the
citation for the rule actually applied so a reviewer can audit it.

The string ``"EBCS_3"`` is still accepted as a **deprecated alias** for
``EBCS_2`` because older rows in the database were written that way; it is
never reported back out as a design code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import UNIT_WEIGHTS_KG_PER_M
from app.utils.concrete_grades import (
    ALPHA_6_FULL_LAP,
    ALPHA_6_STAGGERED,
    CITATION_BS_8666,
    CITATION_EC2,
    CITATION_EBCS_2,
    STANDARD_EC2,
    STANDARD_EBCS_2 as _STANDARD_EBCS_2,
    ConcreteGrade,
    ConcreteGradeError,
    lap_length_ec2,
    parse_grade,
)

# ── Design codes ─────────────────────────────────────────────────────────────
#: ES EN 1992-1-1:2015 -- governs, and is what the app computes by default.
STANDARD_ES_EN_1992_1_1 = STANDARD_EC2
#: EBCS-2:1995 -- withdrawn, retained for site practice and legacy rows.
STANDARD_EBCS_2 = _STANDARD_EBCS_2
#: Shape codes / bend deductions only.
STANDARD_BS_8666 = "BS_8666"

#: Deprecated alias -> the standard it actually meant.
ALIASES: dict[str, str] = {
    "EBCS_3": STANDARD_EBCS_2,   # wrong in the original code; kept for old rows
    "EBCS_2_LEGACY_50D": STANDARD_EBCS_2,  # label written by migration 0004
    "EBCS3": STANDARD_EBCS_2,
    "EBCS-3": STANDARD_EBCS_2,
    "EBCS-2": STANDARD_EBCS_2,
    "EC2": STANDARD_ES_EN_1992_1_1,
    "EN_1992_1_1": STANDARD_ES_EN_1992_1_1,
    "BS8666": STANDARD_BS_8666,
    "BS_8666": STANDARD_BS_8666,
}

DEFAULT_STANDARD = STANDARD_ES_EN_1992_1_1

#: Legacy EBCS-2 site-practice multiple (tension laps). Not a formula -- see
#: ``BBSCalculator.lap_length_detail``.
EBCS_2_LEGACY_LAP_FACTOR = 50

#: Grade assumed when the caller supplies an EC2 lap without a concrete grade.
DEFAULT_GRADE = "C25/30"


class BBSStandardError(ValueError):
    """Raised when a code of practice cannot supply the requested quantity."""


@dataclass(frozen=True)
class CodeOfPractice:
    key: str
    title: str
    citation: str
    #: Whether this code lets us *compute* lap lengths, or only approximate them.
    lap_method: str  # "formula" | "practice" | "none"


CODES_OF_PRACTICE: dict[str, CodeOfPractice] = {
    STANDARD_ES_EN_1992_1_1: CodeOfPractice(
        key=STANDARD_ES_EN_1992_1_1,
        title="ES EN 1992-1-1:2015 (Eurocode 2)",
        citation=CITATION_EC2 + " §8.4",
        lap_method="formula",
    ),
    STANDARD_EBCS_2: CodeOfPractice(
        key=STANDARD_EBCS_2,
        title="EBCS-2:1995 (Structural use of concrete, withdrawn)",
        citation=CITATION_EBCS_2,
        lap_method="practice",
    ),
    STANDARD_BS_8666: CodeOfPractice(
        key=STANDARD_BS_8666,
        title="BS 8666 (Scheduling, dimensioning, cutting and bending)",
        citation=CITATION_BS_8666,
        lap_method="none",
    ),
}


def resolve_standard(standard: str | None) -> CodeOfPractice:
    """Normalise a standard string (including the legacy ``EBCS_3``) to a code."""
    if not standard:
        return CODES_OF_PRACTICE[DEFAULT_STANDARD]
    key = ALIASES.get(standard.strip().upper().replace(" ", "_"), standard.strip())
    try:
        return CODES_OF_PRACTICE[key]
    except KeyError:
        raise BBSStandardError(
            f"Unknown code of practice {standard!r}. Known codes: "
            f"{sorted(CODES_OF_PRACTICE)} (legacy aliases: {sorted(ALIASES)})."
        ) from None


class BBSCalculator:
    BEND_DEDUCTION_FACTOR = 2.0  # 2d per bend

    @staticmethod
    def calculate_cutting_length(
        bar_shape: str,
        clear_length_m: float,
        diameter_mm: int,
        hook_length_mm: int = 0,
        bend_count: int = 1,
        cover_deduction_mm: int = 0,
    ) -> float:
        """
        Returns cutting length in meters.

        Shape handling and bend deductions follow BS 8666 (mandrel diameters
        4*phi up to 16 mm, 7*phi above); the deduction here is the simplified
        2*phi per bend used by the existing take-off sheets.

        cover_deduction_mm is applied to both ends (total = 2 * cover).
        """
        clear_mm = clear_length_m * 1000
        bend_deduction = BBSCalculator.BEND_DEDUCTION_FACTOR * diameter_mm * bend_count

        match bar_shape:
            case "STRAIGHT":
                length = clear_mm + (2 * cover_deduction_mm)
            case "L_SHAPE":
                length = (clear_mm * 2) - bend_deduction + (2 * cover_deduction_mm)
            case "U_SHAPE":
                length = (clear_mm * 2) + hook_length_mm - bend_deduction + (2 * cover_deduction_mm)
            case "HOOK":
                length = clear_mm + hook_length_mm + (2 * cover_deduction_mm)
            case "SPIRAL":
                # Simplified stirrup: 2 legs - 4d bend deductions
                length = (clear_mm * 2) - (4 * diameter_mm)
            case _:
                raise ValueError(f"Unknown bar shape: {bar_shape}")

        return round(length / 1000, 3)

    @staticmethod
    def calculate_weight(diameter_mm: int, length_m: float) -> float:
        """Returns weight in kg."""
        unit_weight = UNIT_WEIGHTS_KG_PER_M.get(diameter_mm, 0.0)
        return round(length_m * unit_weight, 3)

    @classmethod
    def lap_length_detail(
        cls,
        diameter_mm: int,
        standard: str | None = DEFAULT_STANDARD,
        concrete_grade: str | ConcreteGrade | None = None,
        *,
        steel_fyk_mpa: float = 500.0,
        staggered: bool = False,
    ) -> dict:
        """Lap length in mm, with the full calculation trail.

        Returns a dict with ``lap_length_mm`` plus ``design_code``,
        ``citation``, ``method`` and (for EC2) the intermediate strengths, so
        the UI can show a reviewer exactly which rule produced the number.
        """
        code = resolve_standard(standard)

        if code.lap_method == "none":
            raise BBSStandardError(
                f"{code.title} defines shape codes and bend deductions, not lap "
                f"lengths, so this module will not invent one. Use "
                f"{STANDARD_ES_EN_1992_1_1} (formula) or {STANDARD_EBCS_2} "
                f"(site practice) for laps, and {code.key} for cutting lengths."
            )

        if code.lap_method == "practice":
            # Legacy site-practice multiple. Deliberately labelled as an
            # approximation, because it is not derived from EBCS-2 clause 7.x.
            return {
                "lap_length_mm": diameter_mm * EBCS_2_LEGACY_LAP_FACTOR,
                "design_code": code.key,
                "design_code_title": code.title,
                "citation": code.citation,
                "method": "practice_multiple",
                "note": (
                    f"Site-practice multiple of {EBCS_2_LEGACY_LAP_FACTOR}*phi. "
                    f"Not a formula; switch to {STANDARD_ES_EN_1992_1_1} for a "
                    f"derived value."
                ),
            }

        # ── EC2 formula path ────────────────────────────────────────────────
        grade_note: str | None = None
        if concrete_grade is None:
            grade = parse_grade(DEFAULT_GRADE)
            grade_note = (
                f"No concrete grade supplied; assumed {DEFAULT_GRADE}. "
                f"Pass the BoQ grade to price and detail the right mix."
            )
        elif isinstance(concrete_grade, ConcreteGrade):
            grade = concrete_grade
            grade_note = None
        else:
            grade = parse_grade(str(concrete_grade))

        try:
            result = lap_length_ec2(
                diameter_mm,
                grade,
                steel_fyk_mpa,
                alpha_6=ALPHA_6_STAGGERED if staggered else ALPHA_6_FULL_LAP,
            )
        except ConcreteGradeError as exc:
            raise BBSStandardError(str(exc)) from exc

        detail = result.describe()
        detail.update(
            {
                "design_code": code.key,
                "design_code_title": code.title,
                "method": "formula",
                "grade_note": grade_note,
            }
        )
        return detail

    @classmethod
    def calculate_lap_length(
        cls,
        diameter_mm: int,
        standard: str | None = DEFAULT_STANDARD,
        concrete_grade: str | ConcreteGrade | None = None,
        *,
        steel_fyk_mpa: float = 500.0,
        staggered: bool = False,
    ) -> int:
        """Lap length in mm (rounded), per the selected code of practice.

        Defaults to ES EN 1992-1-1:2015 §8.4.4 using a C25/30 mix. Pass
        ``concrete_grade`` from the BoQ to price and detail the actual mix --
        the grade convention changes the answer (see
        :mod:`app.utils.concrete_grades`).
        """
        detail = cls.lap_length_detail(
            diameter_mm,
            standard,
            concrete_grade,
            steel_fyk_mpa=steel_fyk_mpa,
            staggered=staggered,
        )
        return int(round(detail["lap_length_mm"]))

    @classmethod
    def enrich_bar(
        cls,
        bar: dict,
        standard: str | None = DEFAULT_STANDARD,
        concrete_grade: str | ConcreteGrade | None = None,
    ) -> dict:
        """
        Given a bar dict with raw inputs, compute and attach:
        - cutting_length_m
        - weight_per_unit_kg
        - total_weight_kg
        - lap_length_mm, design_code, citation (audit trail)
        """
        cover = max(bar.get("cover_top_mm", 50), bar.get("cover_bottom_mm", 50))
        cutting_length = cls.calculate_cutting_length(
            bar_shape=bar["bar_shape"],
            clear_length_m=float(bar["clear_length_m"]),
            diameter_mm=bar["bar_diameter_mm"],
            hook_length_mm=bar.get("hook_length_mm", 0),
            cover_deduction_mm=cover,
        )
        weight_per_unit = cls.calculate_weight(bar["bar_diameter_mm"], cutting_length)

        lap = cls.lap_length_detail(
            bar["bar_diameter_mm"],
            standard,
            concrete_grade if concrete_grade is not None else bar.get("concrete_grade"),
        )

        return {
            **bar,
            "cutting_length_m": cutting_length,
            "weight_per_unit_kg": weight_per_unit,
            "total_weight_kg": round(weight_per_unit * bar["quantity"], 3),
            "lap_length_mm": int(round(lap["lap_length_mm"])),
            "lap_detail": lap,
            "design_code": lap["design_code"],
            "citation": lap["citation"],
        }
