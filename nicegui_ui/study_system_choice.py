# =============================================================================
# nicegui_ui/study_system_choice.py — Study system and study type as two choices
#
# A study_systems row is one system (annual or semester) for one study type
# (morning or evening), so its id names both. The screens show two selects —
# نظام الدراسة and نوع الدراسة — and this module maps the pair back to the row
# id the database stores (study_system_id). Nothing about what is saved changes.
# =============================================================================

from __future__ import annotations

DAY_LABELS = {"morning": "صباحي", "evening": "مسائي", "parallel": "موازي"}

# The database column study_day_type allows Morning / Evening / Other. Until a
# shifts table exists, "Other" is shown and saved as «موازي» (parallel).
DAY_TO_DB = {"morning": "Morning", "evening": "Evening", "parallel": "Other"}


def normalize_day(raw) -> str:
    d = str(raw or "").strip().lower()
    if d in ("evening", "night", "مسائي", "المسائية", "مسائية", "مساء"):
        return "evening"
    if d in ("other", "parallel", "موازي", "الموازي", "موازية"):
        return "parallel"
    return "morning"


def system_key(row: dict) -> str:
    """Rows that differ only by study type share this key."""
    return f"{row.get('name_ar') or ''}|{row.get('period_display') or ''}"


def split_systems(systems: list[dict]):
    """Return (kinds, days, lookup, by_id).

    kinds  {key: label}             one entry per system, in first-seen order
    days   {day: label}             the study types that exist
    lookup {(key, day): id}
    by_id  {id: (key, day)}
    """
    kinds: dict[str, str] = {}
    days: dict[str, str] = {}
    lookup: dict[tuple[str, str], int] = {}
    by_id: dict[int, tuple[str, str]] = {}
    for s in systems or []:
        sid = s.get("id")
        if sid is None:
            continue
        key = system_key(s)
        day = normalize_day(s.get("study_day_type") or s.get("study_type"))
        kinds.setdefault(key, s.get("name_ar") or "نظام دراسي")
        days.setdefault(day, DAY_LABELS[day])
        lookup.setdefault((key, day), sid)
        by_id[sid] = (key, day)
    # Morning first
    days = {d: days[d] for d in ("morning", "evening", "parallel") if d in days}
    return kinds, days, lookup, by_id


def resolve_system_id(lookup: dict, key: str | None, day: str | None):
    """The study_system_id for a chosen pair, or None when that pair does not exist."""
    return lookup.get((key, day))


class StudySystemPicker:
    """Two selects (system, study type) that read and write one study_system_id via .value."""

    def __init__(self, systems: list[dict], value=None, on_change=None,
                 system_label: str = "نظام الدراسة", day_label: str = "نوع الدراسة",
                 classes: str = "flex-1 min-w-[160px]"):
        from nicegui_ui.ui_components import UI
        self.kinds, self.days, self.lookup, self.by_id = split_systems(systems)
        self._on_change = on_change
        key, day = self.by_id.get(value, (next(iter(self.kinds), None), next(iter(self.days), "morning")))
        self.system_select = UI.select(system_label, self.kinds, value=key, on_change=self._changed).classes(classes)
        self.day_select = UI.select(day_label, self.days, value=day, on_change=self._changed).classes(classes)

    @property
    def value(self):
        return resolve_system_id(self.lookup, self.system_select.value, self.day_select.value)

    @value.setter
    def value(self, sid) -> None:
        if sid in self.by_id:
            key, day = self.by_id[sid]
            self.system_select.value = key
            self.day_select.value = day

    def disable(self) -> None:
        self.system_select.disable()
        self.day_select.disable()

    def _changed(self, _e=None) -> None:
        if self.value is None:
            from nicegui import ui
            ui.notify("هذا النظام غير متاح بهذا النوع من الدراسة", type="warning")
        if self._on_change:
            self._on_change(self.value)


# ── Settings: one block per system, its shifts inside ───────────────────────

RULE_LABELS = {"annual": "حسب السنة (المرحلة)", "semester": "حسب المستوى (المقررات)"}
PERIOD_LABELS = {"year": "سنة", "semester": "فصل"}


def group_systems(systems: list[dict]) -> list[dict]:
    """Rows grouped into systems: {key, name_ar, name_en, rule, period, weights, shifts: [row…]}."""
    groups: dict[str, dict] = {}
    for s in systems or []:
        key = system_key(s)
        g = groups.get(key)
        if g is None:
            g = groups[key] = {
                "key": key,
                "name_ar": s.get("name_ar") or "",
                "name_en": s.get("name_en") or "",
                "rule": s.get("calculation_rule") or "annual",
                "period": s.get("period_display") or "year",
                "weights": s.get("calculation_weights") or "",
                "shifts": [],
            }
        g["shifts"].append({**s, "day": normalize_day(s.get("study_day_type") or s.get("study_type"))})
    order = list(DAY_LABELS)
    for g in groups.values():
        g["shifts"].sort(key=lambda r: order.index(r["day"]))
    return list(groups.values())


def missing_days(group: dict) -> dict[str, str]:
    """The shifts this system does not have yet."""
    have = {r["day"] for r in group.get("shifts", [])}
    return {d: lbl for d, lbl in DAY_LABELS.items() if d not in have}


def system_name_warning(name_ar: str, rule: str, period: str) -> str:
    """A warning when the Arabic name says one system and the rule says another ('' if fine)."""
    name = name_ar or ""
    # النظام الفصلي (two semesters, average by year/stage) and السنوي use the year rule;
    # المقررات (credit hours) uses the level rule.
    says_credits = any(w in name for w in ("مقررات", "المعتمدة"))
    says_yearly = any(w in name for w in ("فصلي", "سنوي"))
    if says_credits and rule == "annual":
        return "الاسم يدل على نظام المقررات لكن الحساب حسب السنة"
    if says_yearly and rule == "semester":
        return "الاسم يدل على النظام الفصلي/السنوي لكن الحساب حسب المستوى"
    if rule == "annual" and period == "semester":
        return "قاعدة الحساب سنوية لكن الفترة فصل"
    return ""
