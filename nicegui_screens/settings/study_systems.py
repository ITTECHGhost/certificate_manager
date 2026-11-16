# =============================================================================
# nicegui_screens/settings/study_systems.py — Settings: study systems
#
# Since migration 0006 the study type (صباحي / مسائي / موازي) is saved on each
# student, so this is a plain list of systems. Rows that a server not yet
# updated still keeps per type are shown as one system: edit, the active switch
# and delete act on all of them together.
# The calculation rule and weights are names/settings only for now (averages
# are entered by hand).
# =============================================================================

from nicegui import ui

from data.repositories import OfflineModeError
from nicegui_ui.study_system_choice import (
    PERIOD_LABELS, RULE_LABELS, group_systems, system_name_warning,
)
from nicegui_ui.ui_components import UI


class StudySystemsMixin:
    """Study systems, one row each (part of SettingsScreen)."""

    def _section_study_systems(self) -> None:
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
                UI.section_label("أنظمة الدراسة")
                # Secondary: the tab's one primary is the university info "حفظ" above
                UI.secondary_button("إضافة نظام", icon="add", on_click=lambda: self._system_dialog(None))
            UI.muted_label("نوع الدراسة (صباحي، مسائي، موازي) يُختار لكل طالب في بياناته.")
            self._systems_container = ui.column().classes("w-full gap-3")
            self._render_systems_list()

    def _reload_systems(self) -> None:
        self._load_data()
        self._render_systems_list()

    def _render_systems_list(self) -> None:
        self._systems_container.clear()
        with self._systems_container:
            groups = group_systems(self.systems)
            if not groups:
                UI.empty_state("لا توجد أنظمة دراسية", "أضف أول نظام.", icon="school")
                return
            for g in groups:
                warn = system_name_warning(g["name_ar"], g["rule"], g["period"])
                with ui.column().classes("app-system-block w-full gap-2"):
                    with ui.row().classes("w-full items-center no-wrap gap-3"):
                        with ui.column().classes("flex-1 min-w-0 gap-0"):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(g["name_ar"] or "—").classes("app-text-primary font-semibold")
                                ui.label(g["name_en"]).classes("app-caption")
                                if warn:
                                    with ui.label("تعارض").classes("app-chip app-chip--warning"):
                                        ui.tooltip(warn)
                            ui.label(" • ".join(x for x in (
                                f"الحساب: {RULE_LABELS.get(g['rule'], g['rule'])}",
                                f"الفترة: {PERIOD_LABELS.get(g['period'], g['period'])}",
                            ) if x)).classes("app-caption")
                        UI.switch("", value=any(bool(r.get("is_active", 1)) for r in g["shifts"]),
                                  on_change=lambda e, grp=g: self._toggle_group_active(grp, e.value))
                        UI.icon_button("edit", "تعديل النظام", on_click=lambda _e, grp=g: self._system_dialog(grp), dense=True)
                        UI.danger_icon_button("delete", "حذف النظام",
                                              on_click=lambda _e, grp=g: self._confirm_delete_group(grp))

    def _add_study_system(self) -> None:
        """Opens the new-system dialog (kept name: other code calls it)."""
        self._system_dialog(None)

    # ── Add / edit a system ─────────────────────────────────────────────────

    def _system_dialog(self, group) -> None:
        """New system, or edit one (the change applies to every row it still has)."""
        is_new = group is None
        g = group or {"name_ar": "", "name_en": "", "rule": "annual", "period": "year",
                      "weights": "10:20:30:40", "shifts": []}
        with ui.dialog() as dlg, UI.card().classes("w-[560px] max-w-full gap-4"):
            UI.card_header("إضافة نظام دراسي" if is_new else f"تعديل النظام: {g['name_ar']}", "school")
            with ui.element("div").classes("app-two-col"):
                name_ar = UI.text_input("اسم النظام بالعربية", value=g["name_ar"])
                name_en = UI.text_input("اسم النظام بالإنكليزية", value=g["name_en"])
                rule = UI.select("قاعدة الحساب", dict(RULE_LABELS), value=g["rule"])
                period = UI.select("الفترة", dict(PERIOD_LABELS), value=g["period"])
            # Weights are not used yet (averages are entered by hand)
            with ui.expansion("خيارات متقدمة", icon="tune").classes("w-full"):
                weights = UI.text_input("الأوزان", value=g["weights"], placeholder="10:20:30:40")
                UI.muted_label("غير مستخدمة حاليًا: المعدل يُدخل يدويًا.")
            warn_lbl = ui.label("").classes("app-chip app-chip--warning")
            warn_lbl.set_visibility(False)

            def _check(_e=None):
                w = system_name_warning(name_ar.value, rule.value, period.value)
                warn_lbl.set_text(w)
                warn_lbl.set_visibility(bool(w))

            for el in (name_ar, rule, period):
                el.on_value_change(_check)
            _check()

            def _save():
                n_ar, n_en = (name_ar.value or "").strip(), (name_en.value or "").strip()
                if not n_ar or not n_en:
                    ui.notify("اكتب اسم النظام بالعربية والإنكليزية", type="warning")
                    return
                w = (weights.value or "").strip() or None
                try:
                    if is_new:
                        self.sys_repo.insert(name_ar=n_ar, name_en=n_en, calc_rule=rule.value,
                                             period_display=period.value, calculation_weights=w,
                                             study_day_type="Morning")
                    else:
                        for r in g["shifts"]:
                            self.sys_repo.update(sys_id=int(r["id"]), name_ar=n_ar, name_en=n_en,
                                                 calc_rule=rule.value, period_display=period.value,
                                                 calculation_weights=w, study_day_type=r.get("study_day_type"),
                                                 is_active=r.get("is_active", 1))
                    ui.notify("تم حفظ النظام الدراسي", type="positive")
                    dlg.close()
                    self._reload_systems()
                except OfflineModeError as err:
                    ui.notify(str(err), type="warning")
                except Exception as err:
                    ui.notify(f"تعذر الحفظ: {err}", type="negative")

            with ui.row().classes("app-dialog-actions"):
                UI.ghost_button("إلغاء", on_click=dlg.close)
                UI.primary_button("حفظ", icon="save", on_click=_save)
        dlg.open()

    # ── Active switch and delete ────────────────────────────────────────────

    def _toggle_group_active(self, group: dict, active: bool) -> None:
        for r in group["shifts"]:
            self._toggle_system_active(int(r["id"]), active)

    def _toggle_system_active(self, sys_id: int, active: bool) -> None:
        try:
            self.sys_repo.toggle(sys_id, 1 if active else 0)
            ui.notify("تم تحديث حالة النظام", type="positive")
        except Exception as exc:
            ui.notify(f"تعذر تحديث الحالة: {exc}", type="negative")

    def _confirm_delete_group(self, group: dict) -> None:
        UI.confirm_dialog(
            "حذف النظام",
            f"سيُحذف ({group.get('name_ar', '')}). لا يمكن حذفه إذا كان مرتبطًا بطلاب أو أوامر تخرج.",
            "حذف",
            lambda: [self._delete_study_system(int(r["id"])) for r in group["shifts"]],
        )

    def _delete_study_system(self, sys_id: int) -> None:
        try:
            self.sys_repo.delete(sys_id)
            ui.notify("تم حذف نظام الدراسة", type="info")
            self._reload_systems()
        except Exception as exc:
            ui.notify(f"تعذر حذف النظام: {exc}", type="negative")
