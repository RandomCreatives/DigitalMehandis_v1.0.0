"""Tests for the concrete grade convention engine.

The point of these tests: the same text ("C-25") can mean two different mixes,
and the app must never lose track of which one it used.
"""

import pytest

from app.utils.bbs_calculator import BBSCalculator
from app.utils.concrete_grades import (
    CITATION_EC2,
    CITATION_EBCS_2,
    STANDARD_EBCS_2,
    STANDARD_EC2,
    ConcreteGradeError,
    cube_spec_from_cylinder,
    cylinder_spec_from_cube,
    f_ctm_mpa,
    lap_length_ec2,
    parse_grade,
)


# ── Parsing ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["C25/30", "c25/30", "C 25 / 30", "C-25/30"])
def test_pair_notation_is_unambiguous(text):
    grade = parse_grade(text)
    assert grade.fck_cyl_mpa == 25.0
    assert grade.fcu_cube_mpa == 30.0
    assert grade.convention == "CYLINDER"
    assert grade.convention_inferred is False
    assert grade.rate_key == "C25/30"


def test_single_number_cube_convention_ebcs():
    """'C-25' read under EBCS-2: f_cu = 25, so f_ck,cyl = 20."""
    grade = parse_grade("C-25", standard=STANDARD_EBCS_2)
    assert grade.fcu_cube_mpa == 25.0
    assert grade.fck_cyl_mpa == 20.0
    assert grade.convention == "CUBE"
    assert grade.rate_key == "C20/25"
    assert grade.convention_inferred is True
    assert grade.warnings  # must warn that the convention was assumed


def test_single_number_cylinder_convention_ec2():
    """'C-25' read under EC2: f_ck,cyl = 25, so f_cu = 31.25 -> C25/30."""
    grade = parse_grade("C-25", standard=STANDARD_EC2)
    assert grade.fck_cyl_mpa == 25.0
    assert grade.fcu_cube_mpa == 31.25
    # 31.25 is not a mix anyone sells; the rate key snaps to the EN 206 class.
    assert grade.exact_rate_key == "C25/31.25"
    assert grade.rate_key == "C25/30"
    assert grade.describe()["rate_key_note"]


def test_same_text_different_mix():
    """The core trap: identical BoQ text, two different concrete mixes."""
    cube = parse_grade("C-25", standard=STANDARD_EBCS_2)
    cylinder = parse_grade("C-25", standard=STANDARD_EC2)
    assert cube.raw == cylinder.raw
    assert cube.fck_cyl_mpa != cylinder.fck_cyl_mpa
    assert cube.rate_key != cylinder.rate_key


@pytest.mark.parametrize("text", ["", "M25", "C-", "25", "C-100500"])
def test_bad_grades_are_rejected(text):
    with pytest.raises(ConcreteGradeError):
        parse_grade(text)


def test_conversion_helpers_round_trip():
    assert cylinder_spec_from_cube(30) == 24.0
    assert cube_spec_from_cylinder(25) == 31.25


def test_reversed_pair_is_flagged():
    """Someone pasting cube/cylinder backwards should be warned, not trusted."""
    grade = parse_grade("C30/25")
    assert grade.warnings


# ── EC2 bond / lap formulae ─────────────────────────────────────────────────

def test_f_ctm_matches_ec2_table_3_1():
    # Table 3.1: C25/30 -> f_ctm = 2.6 MPa, C30/37 -> 2.9 MPa
    assert round(f_ctm_mpa(25), 1) == 2.6
    assert round(f_ctm_mpa(30), 1) == 2.9


def test_lap_length_worked_example():
    """Hand-checkable example: phi16, C25/30, f_yk 500, gamma_c 1.5, a6 = 1.5.

    f_ctm    = 0.30 * 25^(2/3)          = 2.565 MPa
    f_ctk,05 = 0.7 * 2.565              = 1.796 MPa
    f_ctd    = 1.796 / 1.5              = 1.197 MPa
    f_bd     = 2.25 * 1.0 * 1.0 * 1.197 = 2.693 MPa
    sigma_sd = 500 / 1.15               = 434.8 MPa
    l_b,rqd  = (16/4) * 434.8 / 2.693   = 645.7 mm
    l_0      = 1.5 * 645.7              = 968.6 mm
    """
    result = lap_length_ec2(16, parse_grade("C25/30"))
    assert round(result.f_bd_mpa, 2) == 2.69
    assert round(result.l_b_rqd_mm, 1) == 645.7
    assert round(result.lap_length_mm, 1) == 968.6


def test_lap_minimum_governs_for_small_bars_rich_mix():
    """l_0,min = max(0.3*a6*l_b,rqd, 15*phi, 200mm) must be applied."""
    result = lap_length_ec2(6, parse_grade("C50/60"))
    assert result.lap_length_mm >= 200


# ── Integration: the grade reaches the BBS ─────────────────────────────────

def test_grade_convention_changes_the_scheduled_lap():
    """Same bar, same 'C-25' BoQ text, two conventions -> 155 mm difference."""
    cube = parse_grade("C-25", standard=STANDARD_EBCS_2)
    cylinder = parse_grade("C-25", standard=STANDARD_EC2)
    lap_cube = BBSCalculator.calculate_lap_length(16, STANDARD_EC2, cube)
    lap_cylinder = BBSCalculator.calculate_lap_length(16, STANDARD_EC2, cylinder)
    assert lap_cube == 1124
    assert lap_cylinder == 969


def test_lap_detail_carries_its_citation():
    detail = BBSCalculator.lap_length_detail(20, STANDARD_EC2, "C30/37")
    assert detail["design_code"] == "ES_EN_1992_1_1"
    assert detail["citation"].startswith(CITATION_EC2)
    assert detail["grade"]["citation"] == CITATION_EC2
    # everything a reviewer needs to reproduce the number is present
    for key in ("f_bd_mpa", "f_ctd_mpa", "sigma_sd_mpa", "l_b_rqd_mm", "alpha"):
        assert key in detail


def test_ebcs_citation_names_the_right_code():
    grade = parse_grade("C-25", standard=STANDARD_EBCS_2)
    assert grade.citation == CITATION_EBCS_2
    assert "EBCS-2" in grade.citation
    assert "cube" in grade.citation
