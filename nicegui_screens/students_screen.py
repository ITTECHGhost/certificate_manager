# =============================================================================
# nicegui_screens/students_screen.py — NiceGUI Students Management Screen
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles
from nicegui_ui.state import app_session
from data.repositories import StudentRepository


class StudentsScreen:
    """
    NiceGUI Students Management Screen.
    Provides throttled student search, results table with dynamic slots,
    and profile action triggers.
    """

    def __init__(self) -> None:
        self.repo = StudentRepository()
        self.search_input = None
        self.table = None
        self.build_ui()

    def build_ui(self) -> None:
        """Constructs the Students Management view layout."""
        app_session.apply_theme_mode()

        with ui.column().classes("w-full max-w-6xl mx-auto gap-6 p-8"):
            UI.section_header("إدارة الطلاب — Students Management")

            self.search_input = ui.input(
                placeholder="ابحث بالاسم (Search by name)..."
            ).classes("w-full max-w-md").on(
                "update:model-value", self.perform_search, throttle=300
            ).props("outlined")

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
            ).props("flat bordered").classes(Styles.TABLE_CLASSES)

            self.table.add_slot("body-cell-actions", """
                <q-td :props="props">
                    <q-btn size="sm" color="primary" label="View Profile" @click="$parent.$emit('view_profile', props.row)" />
                </q-td>
            """)

            self.table.on("view_profile", self._on_view_profile)

    def perform_search(self, event) -> None:
        """Throttled search handler for student records."""
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
