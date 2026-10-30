BAR_DIAMETERS = [6, 8, 10, 12, 16, 20, 25, 32]

BAR_SHAPES = ["STRAIGHT", "L_SHAPE", "HOOK", "U_SHAPE", "SPIRAL"]

DRAWING_CATEGORIES = ["ARCHITECTURAL", "STRUCTURAL", "ELECTRICAL", "SANITARY"]

SECTIONS = ["SUBSTRUCTURE", "SUPERSTRUCTURE"]

#: Codes of practice recognised by the app.
#: NOTE: "EBCS_3" was the old BBS default and is WRONG -- EBCS-3 is Design of
#: Steel Structures. The concrete code is EBCS-2:1995 (cube strength), itself
#: superseded by ES EN 1992-1-1:2015 (cylinder strength). "EBCS_3" survives
#: only as a deprecated alias in app.utils.bbs_calculator.ALIASES.
CODES_OF_PRACTICE = ["ES_EN_1992_1_1", "EBCS_2", "BS_8666", "IS_CODE"]

#: Strength convention per code -- see app.utils.concrete_grades.
GRADE_STANDARDS = {
    "EBCS_2": "CUBE",
    "ES_EN_1992_1_1": "CYLINDER",
}

USER_ROLES = ["QS_PROFESSIONAL", "STUDENT", "CONTRACTOR", "ADMIN"]

UNIT_WEIGHTS_KG_PER_M = {
    6: 0.222,
    8: 0.395,
    10: 0.617,
    12: 0.888,
    16: 1.578,
    20: 2.466,
    25: 3.853,
    32: 6.313,
}

# WBS categories for take-off sheet
WBS_CATEGORIES = {
    "SUBSTRUCTURE": [
        "1.1 Excavation & Site Work",
        "1.2 Foundations (Footings, Trenches, Walls)",
        "1.3 Plinth Beams & Basement",
        "1.4 Backfilling",
    ],
    "SUPERSTRUCTURE": [
        "2.1 Columns & Walls",
        "2.2 Beams",
        "2.3 Slabs & Floors",
        "2.4 Stairs",
        "2.5 Roofing",
        "2.6 Doors & Windows",
        "2.7 Finishes (Plastering, Painting, Tiles)",
        "2.8 MEP (Electrical, Sanitary, HVAC)",
    ],
}
