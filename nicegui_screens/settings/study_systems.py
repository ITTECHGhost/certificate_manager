# =============================================================================
# nicegui_screens/settings/study_systems.py — Settings: study systems
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_components import UI


class StudySystemsMixin:
    """Study systems list: add, toggle active, delete (part of SettingsScreen)."""

    def _section_study_systems(self) -> None:
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
                UI.section_label("أنظمة الدراسة — Study Systems")
                ui.button("+ إضافة نظام", color=None, on_click=self._add_study_system).classes(
                    "app-btn-primary text-sm px-4 py-2 rounded-lg normal-case font-medium"
                )

            self._systems_container = ui.column().classes("w-full")
            self._render_systems_list()

    def _render_systems_list(self) -> None:
        """Renders a clean, minimal flat table for study systems — no decorative colors."""
        self._systems_container.clear()
        with self._systems_container:
            if not self.systems:
                ui.label("لا توجد أنظمة دراسية معرفة. / No study systems defined.").classes(
                    "app-text-muted text-sm italic py-4 px-2"
                )
                return

            cols = [
                {"name": "name",    "label": "System / النظام",         "field": "name",    "align": "left"},
                {"name": "rule",    "label": "Calc Rule",                "field": "rule",    "align": "center"},
                {"name": "display", "label": "Period",                   "field": "display", "align": "center"},
                {"name": "weights", "label": "Weights",                  "field": "weights", "align": "center"},
                {"name": "active",  "label": "Active",                   "field": "active",  "align": "center"},
                {"name": "actions", "label": "حذف / Delete",                     "field": "actions", "align": "right"},
            ]
            rows = [
                {
                    "id": s.get("id"),
                    "name": f"{s.get('name_ar', '')} / {s.get('name_en', '')}",
                    "rule": s.get("calculation_rule", "annual"),
                    "display": s.get("period_display", "year"),
                    "weights": s.get("calculation_weights", "—"),
                    "is_active": bool(s.get("is_active", 1)),
                }
                for s in self.systems
            ]

            table = (
                ui.table(columns=cols, rows=rows, row_key="id")
                .classes("w-full app-table")
                .props("flat dense separator='horizontal' hide-bottom")
            )

            table.add_slot('body-cell-active', '''
                <q-td :props="props" class="text-center">
                    <q-toggle
                        :model-value="props.row.is_active"
                        @update:model-value="(val) => $parent.$emit('toggle-active', {id: props.row.id, val: val})"
                        dense color="primary"
                    />
                </q-td>
            ''')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props" class="text-right">
                    <q-btn
                        icon="delete"
                        flat round dense size="sm" color="negative"
                        @click="$parent.$emit('delete-system', props.row.id)"
                    />
                </q-td>
            ''')

            table.on('toggle-active', lambda e: self._toggle_system_active(e.args['id'], e.args['val']))
            table.on('delete-system', lambda e: self._delete_study_system(e.args))

    def _add_study_system(self) -> None:
        try:
            self.sys_repo.insert(
                name_ar="نظام جديد",
                name_en="New System",
                calc_rule="annual",
                period_display="year",
                calculation_weights="10:20:30:40"
            )
            ui.notify("تمت إضافة نظام الدراسة بنجاح / Study system added!", type="positive")
            self._load_data()
            self._render_systems_list()
        except Exception as exc:
            ui.notify(f"Error adding study system: {exc}", type="negative")

    def _toggle_system_active(self, sys_id: int, active: bool) -> None:
        try:
            self.sys_repo.toggle(sys_id, 1 if active else 0)
            ui.notify("System status updated!", type="positive")
        except Exception as exc:
            ui.notify(f"Error updating status: {exc}", type="negative")

    def _delete_study_system(self, sys_id: int) -> None:
        try:
            self.sys_repo.delete(sys_id)
            ui.notify("تم حذف نظام الدراسة / System deleted!", type="info")
            self._load_data()
            self._render_systems_list()
        except Exception as exc:
            ui.notify(f"Error deleting system: {exc}", type="negative")
