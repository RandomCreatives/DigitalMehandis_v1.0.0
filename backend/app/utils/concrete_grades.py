"""
Concrete grade conventions for the Ethiopian market.

Why this module exists
----------------------
Ethiopian BoQ line items say "C-25". Drawings say "C25/30". Those are **not
the same mix**, because the two documents use two different code families:

  * EBCS-2:1995                  -> **cube** strength  (f_cu)
  * ES EN 1992-1-1:2015 (EC2)    -> **cylinder** strength (f_ck,cyl)

The relationship is approximately::

    f_ck,cyl  ~=  0.80 * f_cu

So "C-25" read as an EBCS-2 cube grade is a RICHER mix than "C-25" read as an
EC2 cylinder grade (f_ck,cyl = 20 MPa). Pricing the wrong convention silently
mis-prices the concrete on every line -- and nobody notices until a cube test
fails on site.

ES EN 1992-1-1:2015 superseded and withdrew EBCS-2:1995, but Ethiopian site
practice still says "EBCS". So this module *supports both conventions* and
always carries the convention alongside the number. Every grade that leaves
this module knows which standard it is expressed in.

Nothing here is guessed: the EC2 bond/lap formulae are the ones cited in the
docstrings, and the defaults are configurable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal

# ── Standards ────────────────────────────────────────────────────────────────
#: Cube-strength convention (EBCS-2:1995, withdrawn by EC2 but still quoted on site)
STANDARD_EBCS_2 = "EBCS_2"
#: Cylinder-strength convention (ES EN 1992-1-1:2015)
STANDARD_EC2 = "ES_EN_1992_1_1"

StrengthConvention = Literal["CUBE", "CYLINDER"]

CONVENTION_BY_STANDARD: dict[str, StrengthConvention] = {
    STANDARD_EBCS_2: "CUBE",
    STANDARD_EC2: "CYLINDER",
}

#: EC2 (and the EN 206 / ES EN 206 family): f_ck,cyl ~= 0.80 * f_cu
CYLINDER_FROM_CUBE_FACTOR = 0.80

#: Tolerated parse of a "C-25" style grade when no standard is supplied.
DEFAULT_STANDARD = STANDARD_EC2

#: EN 206 / ES EN 206 standard strength classes as (f_ck,cyl, f_cu,cube).
#: Suppliers quote these pairs, so the rate library must be keyed on them --
#: a derived "C25/31.25" is not a mix anybody can sell you.
STANDARD_GRADE_PAIRS: tuple[tuple[float, float], ...] = (
    (12.0, 15.0),
    (16.0, 20.0),
    (20.0, 25.0),
    (25.0, 30.0),
    (30.0, 37.0),
    (35.0, 45.0),
    (40.0, 50.0),
    (45.0, 55.0),
    (50.0, 60.0),
)

#: How far a derived cube strength may drift before we refuse to snap it onto
#: a named EN 206 class (MPa).
RATE_KEY_SNAP_TOLERANCE_MPA = 3.0

CITATION_EBCS_2 = "EBCS-2:1995 (cube strength; withdrawn by ES EN 1992-1-1:2015)"
CITATION_EC2 = "ES EN 1992-1-1:2015 (cylinder strength)"
CITATION_BS_8666 = "BS 8666 (shape codes and bend deductions only; no lap formula)"


class ConcreteGradeError(ValueError):
    """Raised when a grade string cannot be interpreted unambiguously."""


@dataclass(frozen=True)
class ConcreteGrade:
    """A concrete grade that always carries its strength convention.

    Construct via :func:`parse_grade` rather than directly.
    """

    fck_cyl_mpa: float
    fcu_cube_mpa: float
    standard: str
    #: Raw text as it appeared in the source document (BoQ line, drawing note).
    raw: str
    #: True when the source text only had one number ("C-25") and the
    #: convention therefore had to come from project settings rather than
    #: from the document itself.
    convention_inferred: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def convention(self) -> StrengthConvention:
        return CONVENTION_BY_STANDARD.get(self.standard, "CYLINDER")

    @property
    def exact_rate_key(self) -> str:
        """The literal cylinder/cube pair derived from the source text."""
        return f"C{_fmt(self.fck_cyl_mpa)}/{_fmt(self.fcu_cube_mpa)}"

    @property
    def rate_key(self) -> str:
        """Canonical key for the unit-rate library: cylinder/cube, e.g. ``C20/25``.

        Rate rows must be keyed on this, never on the bare "C-25" string, so a
        cube-priced rate can never be matched against a cylinder-specified item.

        Where the source text carried one number and the convention had to be
        inferred, the derived pair is snapped onto the nearest EN 206 class the
        market actually sells (within :data:`RATE_KEY_SNAP_TOLERANCE_MPA`).
        """
        return self._snapped_pair()[0]

    def _snapped_pair(self) -> tuple[str, tuple[float, float] | None]:
        exact = self.exact_rate_key
        best: tuple[float, tuple[float, float]] | None = None
        for cyl, cube in STANDARD_GRADE_PAIRS:
            if abs(cube - self.fcu_cube_mpa) > RATE_KEY_SNAP_TOLERANCE_MPA:
                continue
            distance = abs(cyl - self.fck_cyl_mpa) + abs(cube - self.fcu_cube_mpa)
            if best is None or distance < best[0]:
                best = (distance, (cyl, cube))
        if best is None:
            return exact, None
        cyl, cube = best[1]
        return f"C{_fmt(cyl)}/{_fmt(cube)}", (cyl, cube)

    @property
    def citation(self) -> str:
        return CITATION_EC2 if self.standard == STANDARD_EC2 else CITATION_EBCS_2

    def describe(self) -> dict:
        """Audit-friendly dict — safe to serialise into a quantity line's provenance."""
        key, snapped = self._snapped_pair()
        note = None
        if snapped is not None and key != self.exact_rate_key:
            note = (
                f"Rate key snapped from derived {self.exact_rate_key} to the "
                f"nearest standard EN 206 class {key}."
            )
        return {
            "raw": self.raw,
            "standard": self.standard,
            "convention": self.convention,
            "fck_cyl_mpa": self.fck_cyl_mpa,
            "fcu_cube_mpa": self.fcu_cube_mpa,
            "rate_key": key,
            "rate_key_exact": self.exact_rate_key,
            "rate_key_note": note,
            "convention_inferred": self.convention_inferred,
            "warnings": list(self.warnings),
            "citation": self.citation,
        }


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


# Accepts: C-25, C25, C 25, C25/30, C-25/30, c25 / 30, "C25/30 (cylinder)"
_GRADE_RE = re.compile(
    r"^\s*[Cc]\s*[-–]?\s*(\d{2})\s*(?:/\s*(\d{2}))?\s*$"
)


def parse_grade(text: str, standard: str | None = None) -> ConcreteGrade:
    """Parse an Ethiopian concrete grade string into a convention-aware grade.

    Args:
        text: e.g. ``"C-25"``, ``"C25/30"``, ``"c25"``.
        standard: the convention to apply when ``text`` carries only one number.
            Defaults to :data:`DEFAULT_STANDARD` (EC2 / cylinder) and flags the
            result as ``convention_inferred`` so the UI can ask the user.

    Returns:
        ConcreteGrade

    Raises:
        ConcreteGradeError: if the string is not a recognisable grade.

    Examples:
        >>> parse_grade("C25/30").rate_key
        'C25/30'
        >>> parse_grade("C-25", standard=STANDARD_EBCS_2).fck_cyl_mpa
        20.0
        >>> parse_grade("C-25", standard=STANDARD_EC2).fcu_cube_mpa
        31.25
    """
    match = _GRADE_RE.match(text or "")
    if not match:
        raise ConcreteGradeError(
            f"Unrecognised concrete grade {text!r}. Expected forms like "
            f"'C-25', 'C25' or 'C25/30'."
        )

    cyl_text, cube_text = match.group(1), match.group(2)

    if cube_text is not None:
        # "C25/30" is unambiguous: cylinder / cube, per EN 206 notation.
        fck = float(cyl_text)
        fcu = float(cube_text)
        return ConcreteGrade(
            fck_cyl_mpa=fck,
            fcu_cube_mpa=fcu,
            standard=STANDARD_EC2,
            raw=text,
            convention_inferred=False,
            warnings=_convention_warnings(fck, fcu),
        )

    declared = standard or DEFAULT_STANDARD
    if declared not in CONVENTION_BY_STANDARD:
        raise ConcreteGradeError(
            f"Unknown grade standard {declared!r}. "
            f"Expected one of {sorted(CONVENTION_BY_STANDARD)}."
        )

    value = float(cyl_text)
    if CONVENTION_BY_STANDARD[declared] == "CUBE":
        fcu = value
        fck = value * CYLINDER_FROM_CUBE_FACTOR
    else:
        fck = value
        fcu = value / CYLINDER_FROM_CUBE_FACTOR

    return ConcreteGrade(
        fck_cyl_mpa=round(fck, 2),
        fcu_cube_mpa=round(fcu, 2),
        standard=declared,
        raw=text,
        convention_inferred=True,
        warnings=(
            f"'{text}' gives no strength convention; read as "
            f"{CONVENTION_BY_STANDARD[declared].lower()} per {declared}. "
            f"Confirm against the specification.",
        ),
    )


def _convention_warnings(fck: float, fcu: float) -> tuple[str, ...]:
    """Flag grade pairs whose ratio is far from the usual 0.80 relationship."""
    if fck <= 0 or fcu <= 0:
        return ("Grade values must be positive.",)
    ratio = fck / fcu
    if not 0.70 <= ratio <= 0.90:
        return (
            f"f_ck/f_cu ratio is {ratio:.2f}, outside the usual 0.70-0.90 band "
            f"for Ethiopian practice. Check whether the pair is reversed "
            f"(cube/cylinder) or copied from a different specification.",
        )
    return ()


# ── EC2 bond & lap (§8.4) ────────────────────────────────────────────────────

@dataclass(frozen=True)
class LapResult:
    """A lap/anchorage length with the full calculation trail attached."""

    lap_length_mm: float
    l_b_rqd_mm: float
    f_bd_mpa: float
    f_ctd_mpa: float
    sigma_sd_mpa: float
    alpha: dict[str, float]
    diameter_mm: int
    grade: ConcreteGrade
    citation: str

    def describe(self) -> dict:
        return {
            "lap_length_mm": round(self.lap_length_mm, 1),
            "l_b_rqd_mm": round(self.l_b_rqd_mm, 1),
            "f_bd_mpa": round(self.f_bd_mpa, 3),
            "f_ctd_mpa": round(self.f_ctd_mpa, 3),
            "sigma_sd_mpa": round(self.sigma_sd_mpa, 1),
            "alpha": {k: v for k, v in self.alpha.items()},
            "diameter_mm": self.diameter_mm,
            "grade": self.grade.describe(),
            "citation": self.citation,
        }


#: α6 per EC2 Table 8.2 -- 100% lapped / staggered
ALPHA_6_FULL_LAP = 1.5
ALPHA_6_STAGGERED = 1.4


def f_ctm_mpa(fck_cyl: float) -> float:
    """Mean tensile strength, EC2 Table 3.1: f_ctm = 0.30 * f_ck^(2/3) for f_ck <= 50."""
    if fck_cyl <= 0:
        raise ConcreteGradeError("f_ck must be positive")
    if fck_cyl > 50:
        # EC2: f_ctm = 2.12 * ln(1 + (f_cm/10)); f_cm = f_ck + 8
        f_cm = fck_cyl + 8
        return 2.12 * math.log(1 + f_cm / 10)
    return 0.30 * fck_cyl ** (2.0 / 3.0)


def lap_length_ec2(
    diameter_mm: int,
    grade: ConcreteGrade,
    steel_fyk_mpa: float = 500.0,
    *,
    gamma_c: float = 1.5,
    gamma_s: float = 1.15,
    alpha_ct: float = 1.0,
    eta1: float = 1.0,
    eta2: float | None = None,
    alpha_1: float = 1.0,
    alpha_2: float = 1.0,
    alpha_3: float = 1.0,
    alpha_5: float = 1.0,
    alpha_6: float = ALPHA_6_FULL_LAP,
) -> LapResult:
    """Design lap length ``l_0`` per ES EN 1992-1-1:2015 §8.4.4 / §8.4.3.

    .. code-block:: text

        f_ctd  = alpha_ct * f_ctk,0.05 / gamma_c      (3.1.6)
        f_ctk,0.05 = 0.7 * f_ctm
        f_bd   = 2.25 * eta1 * eta2 * f_ctd           (8.4.2)
        sigma_sd = f_yk / gamma_s                     (3.2.7)
        l_b,rqd = (phi / 4) * (sigma_sd / f_bd)       (8.4.3)
        l_0    = a1*a2*a3*a5*a6 * l_b,rqd             (8.4.4)
        l_0   >= max(0.3 * a6 * l_b,rqd, 15*phi, 200) (8.4.4)

    Defaults: γ_c = 1.5 (persistent, unfavourable), γ_s = 1.15, η1 = 1.0
    ("good" bond conditions), η2 = 1.0 for φ ≤ 32 mm, α6 = 1.5 for 100 %
    lapped bars (use 1.4 where laps are staggered).

    All coefficients are arguments rather than constants so a reviewer can
    reproduce any number the app prints.
    """
    if diameter_mm <= 0:
        raise ConcreteGradeError("Bar diameter must be positive")
    if eta2 is None:
        eta2 = 1.0 if diameter_mm <= 32 else 0.7

    f_ctm = f_ctm_mpa(grade.fck_cyl_mpa)
    f_ctk_005 = 0.7 * f_ctm
    f_ctd = alpha_ct * f_ctk_005 / gamma_c
    f_bd = 2.25 * eta1 * eta2 * f_ctd
    sigma_sd = steel_fyk_mpa / gamma_s

    l_b_rqd = (diameter_mm / 4.0) * (sigma_sd / f_bd)
    alpha_product = alpha_1 * alpha_2 * alpha_3 * alpha_5 * alpha_6
    l_0 = alpha_product * l_b_rqd
    l_0_min = max(0.3 * alpha_6 * l_b_rqd, 15 * diameter_mm, 200.0)

    return LapResult(
        lap_length_mm=max(l_0, l_0_min),
        l_b_rqd_mm=l_b_rqd,
        f_bd_mpa=f_bd,
        f_ctd_mpa=f_ctd,
        sigma_sd_mpa=sigma_sd,
        alpha={
            "alpha_1": alpha_1,
            "alpha_2": alpha_2,
            "alpha_3": alpha_3,
            "alpha_5": alpha_5,
            "alpha_6": alpha_6,
        },
        diameter_mm=diameter_mm,
        grade=grade,
        citation=CITATION_EC2 + " §8.4.4",
    )


def cube_spec_from_cylinder(fck_cyl_mpa: float) -> float:
    """Cylinder strength -> the cube strength a supplier should quote (f_cu)."""
    return round(fck_cyl_mpa / CYLINDER_FROM_CUBE_FACTOR, 2)


def cylinder_spec_from_cube(fcu_cube_mpa: float) -> float:
    """Cube strength -> design cylinder strength f_ck,cyl."""
    return round(fcu_cube_mpa * CYLINDER_FROM_CUBE_FACTOR, 2)
