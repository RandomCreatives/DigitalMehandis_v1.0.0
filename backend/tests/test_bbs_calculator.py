"""Unit tests for BBS calculation logic."""
import pytest
from app.utils.bbs_calculator import BBSStandardError, BBSCalculator


def test_straight_bar_cutting_length():
    result = BBSCalculator.calculate_cutting_length(
        bar_shape="STRAIGHT",
        clear_length_m=2.4,
        diameter_mm=16,
        cover_deduction_mm=50,
    )
    # 2400 + 2*50 = 2500mm = 2.5m
    assert result == 2.5


def test_l_shape_bar_cutting_length():
    result = BBSCalculator.calculate_cutting_length(
        bar_shape="L_SHAPE",
        clear_length_m=2.4,
        diameter_mm=16,
        cover_deduction_mm=50,
    )
    # (2400*2) - (2*16) + (2*50) = 4800 - 32 + 100 = 4868mm = 4.868m
    assert abs(result - 4.868) < 0.001


def test_hook_bar_cutting_length():
    result = BBSCalculator.calculate_cutting_length(
        bar_shape="HOOK",
        clear_length_m=3.0,
        diameter_mm=12,
        hook_length_mm=150,
        cover_deduction_mm=40,
    )
    # 3000 + 150 + 2*40 = 3230mm = 3.23m
    assert result == 3.23


def test_u_shape_bar_cutting_length():
    result = BBSCalculator.calculate_cutting_length(
        bar_shape="U_SHAPE",
        clear_length_m=1.5,
        diameter_mm=10,
        hook_length_mm=100,
        cover_deduction_mm=30,
    )
    # (1500*2) + 100 - (2*10) + (2*30) = 3000 + 100 - 20 + 60 = 3140mm = 3.14m
    assert result == 3.14


def test_steel_weight_16mm():
    weight = BBSCalculator.calculate_weight(diameter_mm=16, length_m=10.0)
    # 16mm unit weight = 1.578 kg/m
    assert abs(weight - 15.78) < 0.01


def test_steel_weight_12mm():
    weight = BBSCalculator.calculate_weight(diameter_mm=12, length_m=5.0)
    # 12mm unit weight = 0.888 kg/m
    assert abs(weight - 4.44) < 0.01


def test_lap_length_ec2_default():
    """Default is now ES EN 1992-1-1:2015 §8.4.4 on a C25/30 mix."""
    lap = BBSCalculator.calculate_lap_length(diameter_mm=16, concrete_grade="C25/30")
    # f_bd = 2.25*1.0*1.0*(0.7*0.30*25^(2/3)/1.5) = 2.693 MPa
    # l_b,rqd = (16/4)*(500/1.15)/2.693 = 645.7 mm ; l_0 = 1.5*l_b,rqd = 968.6 mm
    assert lap == 969


def test_lap_length_ec2_staggered_is_shorter():
    """a6 = 1.4 for staggered laps instead of 1.5 for 100 % lapped (Table 8.2)."""
    full = BBSCalculator.calculate_lap_length(16, concrete_grade="C25/30")
    staggered = BBSCalculator.calculate_lap_length(16, concrete_grade="C25/30", staggered=True)
    assert staggered == 904
    assert staggered < full


def test_lap_length_legacy_ebcs_alias():
    """'EBCS_3' was wrong (Design of Steel Structures). Kept as an alias for
    EBCS_2 so old rows still resolve -- but it never reports EBCS_3 back."""
    assert BBSCalculator.calculate_lap_length(16, "EBCS_3") == 800
    detail = BBSCalculator.lap_length_detail(16, "EBCS_3")
    assert detail["design_code"] == "EBCS_2"
    assert detail["method"] == "practice_multiple"


def test_lap_length_bs_8666_refuses_to_invent_a_lap():
    """BS 8666 defines shape codes and bend deductions, not lap lengths."""
    with pytest.raises(BBSStandardError):
        BBSCalculator.calculate_lap_length(16, "BS_8666")


def test_unknown_standard_raises():
    with pytest.raises(BBSStandardError):
        BBSCalculator.calculate_lap_length(16, "EBCS_9")


def test_enrich_bar():
    bar = {
        "bar_shape": "STRAIGHT",
        "clear_length_m": 2.4,
        "bar_diameter_mm": 16,
        "hook_length_mm": 0,
        "cover_top_mm": 50,
        "cover_bottom_mm": 50,
        "quantity": 10,
    }
    enriched = BBSCalculator.enrich_bar(bar)
    assert enriched["cutting_length_m"] == 2.5
    assert abs(enriched["weight_per_unit_kg"] - 3.945) < 0.01
    assert abs(enriched["total_weight_kg"] - 39.45) < 0.1
    # Default C25/30 under EC2 (see test_lap_length_ec2_default).
    assert enriched["lap_length_mm"] == 969
    assert enriched["design_code"] == "ES_EN_1992_1_1"
    assert "ES EN 1992-1-1:2015" in enriched["citation"]
    assert enriched["lap_detail"]["method"] == "formula"


def test_unknown_shape_raises():
    with pytest.raises(ValueError):
        BBSCalculator.calculate_cutting_length("ZIGZAG", 1.0, 12)
