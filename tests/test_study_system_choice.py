from nicegui_ui.study_system_choice import split_systems, resolve_system_id, normalize_day

SYSTEMS = [
    {"id": 1, "name_ar": "نظام فصلي", "period_display": "year", "study_day_type": "Morning"},
    {"id": 2, "name_ar": "نظام مقررات", "period_display": "semester", "study_day_type": "Morning"},
    {"id": 3, "name_ar": "نظام فصلي", "period_display": "year", "study_day_type": "Evening"},
    {"id": 4, "name_ar": "نظام مقررات", "period_display": "semester", "study_day_type": "Evening"},
    {"id": 5, "name_ar": "ماجستير", "period_display": "semester", "study_day_type": "Morning"},
]


def test_two_choices_instead_of_one_merged_list():
    kinds, days, lookup, by_id = split_systems(SYSTEMS)
    assert list(kinds.values()) == ["نظام فصلي", "نظام مقررات", "ماجستير"]
    assert days == {"morning": "صباحي", "evening": "مسائي"}
    for sid, (key, day) in by_id.items():
        assert resolve_system_id(lookup, key, day) == sid


def test_missing_pair_resolves_to_none():
    kinds, days, lookup, by_id = split_systems(SYSTEMS)
    master = by_id[5][0]
    assert resolve_system_id(lookup, master, "evening") is None


def test_normalize_day():
    assert normalize_day("Evening") == "evening"
    assert normalize_day("مسائي") == "evening"
    assert normalize_day(None) == "morning"
