from nicegui_ui.study_system_choice import (
    DAY_TO_DB, group_systems, missing_days, normalize_day, split_systems, system_name_warning,
)

ROWS = [
    {"id": 1, "name_ar": "نظام سنوي", "name_en": "Annual", "study_day_type": "Morning",
     "calculation_rule": "annual", "period_display": "year", "calculation_weights": "10:20:30:40", "is_active": 1},
    {"id": 2, "name_ar": "نظام مقررات", "name_en": "Semester", "study_day_type": "Morning",
     "calculation_rule": "semester", "period_display": "semester", "is_active": 1},
    {"id": 3, "name_ar": "نظام سنوي", "name_en": "Annual", "study_day_type": "Evening",
     "calculation_rule": "annual", "period_display": "year", "is_active": 0},
    {"id": 5, "name_ar": "نظام سنوي", "name_en": "Annual", "study_day_type": "Other",
     "calculation_rule": "annual", "period_display": "year", "is_active": 1},
]


def test_parallel_is_other_in_the_database():
    assert normalize_day("Other") == "parallel"
    assert normalize_day("موازي") == "parallel"
    assert DAY_TO_DB["parallel"] == "Other"
    _kinds, days, lookup, _ = split_systems(ROWS)
    assert list(days) == ["morning", "evening", "parallel"]
    assert lookup[("نظام سنوي|year", "parallel")] == 5


def test_group_systems_one_block_per_system():
    groups = group_systems(ROWS)
    assert [g["name_ar"] for g in groups] == ["نظام سنوي", "نظام مقررات"]
    assert [r["day"] for r in groups[0]["shifts"]] == ["morning", "evening", "parallel"]
    assert missing_days(groups[0]) == {}
    assert set(missing_days(groups[1])) == {"evening", "parallel"}


def test_name_warning():
    assert system_name_warning("نظام فصلي", "annual", "year")
    assert system_name_warning("نظام سنوي", "semester", "semester")
    assert system_name_warning("نظام سنوي", "annual", "year") == ""
    assert system_name_warning("نظام بولونيا", "semester", "semester") == ""
