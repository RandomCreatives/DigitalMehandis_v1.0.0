"""Unit tests for BBS calculation logic."""
import pytest
from app.modules.bbs.calculator import BBSCalculator


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


def test_lap_length_ebcs():
    lap = BBSCalculator.calculate_lap_length(diameter_mm=16, standard="EBCS_3")
    assert lap == 800  # 50 * 16


def test_lap_length_bs():
    lap = BBSCalculator.calculate_lap_length(diameter_mm=16, standard="BS_8666")
    assert lap == 640  # 40 * 16


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
    assert enriched["lap_length_mm"] == 800


def test_unknown_shape_raises():
    with pytest.raises(ValueError):
        BBSCalculator.calculate_cutting_length("ZIGZAG", 1.0, 12)
