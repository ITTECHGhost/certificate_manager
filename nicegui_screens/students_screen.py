# =============================================================================
# nicegui_screens/students_screen.py — NiceGUI Students Management Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles
from data.repositories import StudentRepository


class StudentsScreen:
    """
    NiceGUI Students Management Screen.
    Provides throttled student search, results table with dynamic slots,
    and profile action triggers inside global UI.card container.
    """

    def __init__(self) -> None:
        self.repo = StudentRepository()
        self.search_input = None
        self.table = None
        self.build_ui()

    def build_ui(self) -> None:
        """Constructs the Students Management view layout using global UI components."""
        with UI.card():
            UI.card_header("إدارة الطلاب — Students Management", "people", icon_css="stat-text-blue")

            with ui.row().classes("w-full items-center justify-between gap-4 mt-2"):
                self.search_input = UI.text_input(
                    label="ابحث بالاسم (Search student by name)",
                    placeholder="أدخل اسم الطالب..."
                ).classes("w-full max-w-md").on(
                    "update:model-value", self.perform_search, throttle=300
                )

            columns = [
                {"name": "name_ar", "label": "Name / الاسم", "field": "name_ar", "align": "left"},
                {"name": "dept_name_ar", "label": "Department / القسم", "field": "dept_name_ar", "align": "left"},
                {"name": "graduation_year", "label": "Grad Year / سنة التخرج", "field": "graduation_year", "align": "center"},
                {"name": "average", "label": "Average / المعدل", "field": "average", "align": "center"},
                {"name": "actions", "label": "Actions / الإجراءات", "field": "actions", "align": "center"},
            ]

            self.table = ui.table(
                columns=columns,
                rows=[],
                row_key="name_ar"
            ).classes(Styles.TABLE_CLASSES).props("flat bordered hide-bottom")

            self.table.add_slot("body-cell-actions", """
                <q-td :props="props">
                    <q-btn size="sm" color="primary" label="View Profile" @click="$parent.$emit('view_profile', props.row)" />
                </q-td>
            """)

            self.table.on("view_profile", self._on_view_profile)


    def perform_search(self, event) -> None:
        """Throttled search handler for student records."""
        if self.table is None:
            return

        if hasattr(event, "value") and event.value is not None:
            query = str(event.value)

        elif isinstance(getattr(event, "args", None), str):
            query = event.args
        elif isinstance(getattr(event, "args", None), dict):
            query = str(event.args.get("value", ""))
        else:
            query = str(getattr(event, "args", "") or "")

        query = query.strip()

        # GUARDRAIL: If query length < 2, clear table and return early
        if len(query) < 2:
            self.table.rows = []
            self.table.update()
            return

        try:
            results = self.repo.search(query, limit=8)
            self.table.rows = results if results else []
            self.table.update()
        except Exception as exc:
            print(f"[StudentsScreen] Search error: {exc}")
            self.table.rows = []
            self.table.update()

    def _on_view_profile(self, msg) -> None:
        """Triggered when the View Profile button is clicked in the table slot."""
        row_data = getattr(msg, "args", {}) or {}
        student_name = row_data.get("name_ar") or row_data.get("name_en") or "Student"
        ui.notify(f"Viewing profile for: {student_name}", type="info")
