"""Tests for repairing OCR damage in scanned government rate booklets.

The cases below are taken verbatim from `data/rates/`, so they are a record of
the real damage, not invented examples.
"""

from decimal import Decimal

import pytest

from app.utils.rate_ocr import (
    CONF_CLEAN,
    CONF_NO_CENTS,
    CONF_REPAIRED,
    check_plausible,
    normalise_unit,
    repair_amount,
    repair_description,
)


# ── Clean amounts pass through untouched ────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("751.11", "751.11"),
        ("3,417.50", "3417.50"),
        ("85,000.00", "85000.00"),
        ("16,215.96", "16215.96"),
        ("2,024.39", "2024.39"),
        ("1,731.63", "1731.63"),
    ],
)
def test_clean_amounts(raw, expected):
    result = repair_amount(raw)
    assert result.value == Decimal(expected)
    assert result.confidence == CONF_CLEAN
    assert result.repairs == ()


# ── Glyph confusion ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("l4.858.24", "14858.24"),   # l -> 1
        ("3,44g.52", "3449.52"),     # g -> 9
        ("23,l06.85", "23106.85"),   # l -> 1
        ("l 9,822.41", "19822.41"),
        ("l 6,369.09", "16369.09"),
    ],
)
def test_glyph_confusion_is_repaired(raw, expected):
    result = repair_amount(raw)
    assert result.value == Decimal(expected)
    assert result.confidence == CONF_REPAIRED
    assert result.repairs


# ── Separator damage ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("19.158.42", "19158.42"),   # dots used as thousands
        ("1,1.77.21", "1177.21"),    # mixed separators
        ("23,50.1.85", "23501.85"),
        ("25,186 85", "25186.85"),   # space as decimal point
        ("8,611 .36", "8611.36"),
        ("I 7,376 92", "17376.92"),  # I -> 1, space as decimal
    ],
)
def test_separator_damage_is_repaired(raw, expected):
    result = repair_amount(raw)
    assert result.value == Decimal(expected)
    assert result.confidence >= CONF_REPAIRED


def test_two_decimal_places_pin_the_decimal_point():
    """The structural rule: cents are always the final two digits."""
    # 'l4.858.24' could naively read as 4.85824; the rule forbids that.
    assert repair_amount("l4.858.24").value == Decimal("14858.24")


# ── Refusals ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw",
    ["SUB STRUCTURE", "", None, "READY MIX CONCRETE WITH STATIONARY PUMP"],
)
def test_non_amounts_are_refused_not_guessed(raw):
    result = repair_amount(raw)
    assert result.value is None
    assert result.problems
    assert result.needs_review


def test_prose_with_digits_is_refused():
    """Page footers carry digits by accident ('2018 3rd Quarter (Only Correct)')."""
    result = repair_amount("20183rd0uarter(0n1y01rectc05t)")
    assert result.value is None
    assert "prose" in result.problems[0]


def test_amount_without_cents_needs_review():
    """Every price in these booklets has cents, so '117' is suspicious."""
    result = repair_amount("117")
    assert result.value == Decimal("117")
    assert result.confidence == CONF_NO_CENTS
    assert result.needs_review


def test_garbage_is_rejected():
    result = repair_amount("LJ99")
    assert result.value is None


# ── Descriptions and units ─────────────────────────────────────────────────

def test_description_repairs_are_conservative():
    text, repairs = repair_description("C-25 Concrete (Mechanical Mix) l:2:3 for l0cm thick slab")
    assert "10cm" in text          # l0cm -> 10cm
    assert "C-25" in text          # a bare digit is never rewritten
    assert repairs


def test_description_does_not_mangle_real_words():
    """Character-wise confusion mapping would turn 'Slab' into '5lab'."""
    text, _ = repair_description("C-15 Concrete for Footing, Beam and Slab")
    assert "Slab" in text
    assert "Footing" in text


def test_cement_quantity_unit_repaired():
    text, repairs = repair_description("R.C. C-25 378 hg of cement per m3 with drum mixer")
    assert "378 kg of cement" in text
    assert repairs


@pytest.mark.parametrize(
    "unit,expected", [("m3", "m³"), ("m2", "m²"), ("m'", "m³"), ("m³", "m³")]
)
def test_unit_normalisation(unit, expected):
    value, _ = normalise_unit(unit)
    assert value == expected


# ── Plausibility ───────────────────────────────────────────────────────────

def test_implausible_amounts_are_flagged():
    assert check_plausible(Decimal("0"), "m³")
    assert check_plausible(Decimal("-5"), "m³")
    assert check_plausible(Decimal("99999999"), "m³")


def test_lean_concrete_per_square_metre_is_flagged():
    problems = check_plausible(Decimal("751.11"), "m²", "C-7 Lean Concrete (Hand mix)")
    assert problems
