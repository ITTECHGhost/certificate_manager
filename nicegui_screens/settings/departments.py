# =============================================================================
# nicegui_screens/settings/departments.py — Departments, inside "University information"
#
# The college is entered once (institution.py); its departments are listed
# below it. A department has two fields, the Arabic and English name, and
# belongs to that college automatically (university_settings_id = 1, as the
# repository already does). Newest first; edit and delete with confirmation.
# =============================================================================

import logging

from nicegui import ui

from data.repositories import DepartmentRepository, OfflineModeError
from nicegui_ui.ui_components import UI

log = logging.getLogger(__name__)


def departments_newest_first(rows: list[dict]) -> list[dict]:
    """Departments with the most recently added (highest id) first."""
    def _key(r):
        try:
            return int(r.get("id") or 0)
        except (TypeError, ValueError):
            return 0
    return sorted(rows or [], key=_key, reverse=True)


class DepartmentsMixin:
    """Department list and two-field add form, shown under the college information."""

    def _section_departments(self) -> None:
        if not getattr(self, "_can_edit_departments", True):
            return
        repo = getattr(self, "dept_repo", None) or DepartmentRepository()

        with UI.card():
            UI.card_header("الأقسام", "business")
            UI.muted_label("كل قسم يتبع الكلية أعلاه.")

            # Add: the two names and one button, on one row (stacks on narrow windows)
            with ui.element("div").classes("app-dept-add w-full"):
                add_ar = UI.text_input("اسم القسم بالعربية")
                add_en = UI.text_input("اسم القسم بالإنكليزية")

                def _add():
                    n_ar = (add_ar.value or "").strip()
                    n_en = (add_en.value or "").strip()
                    if not n_ar or not n_en:
                        ui.notify("اكتب اسم القسم بالعربية والإنكليزية", type="warning")
                        return
                    try:
                        repo.insert(name_ar=n_ar, name_en=n_en)
                        add_ar.value = ""
                        add_en.value = ""
                        ui.notify(f"تمت إضافة القسم ({n_ar})", type="positive")
                        dept_list.refresh()
                    except OfflineModeError as err:
                        ui.notify(str(err), type="warning")
                    except Exception as err:
                        log.error("Error adding department: %s", err)
                        ui.notify(f"تعذر الحفظ: {err}", type="negative")

                add_en.on("keydown.enter", lambda _e: _add())
                UI.primary_button("إضافة قسم", icon="add", on_click=_add)

            @ui.refreshable
            def dept_list():
                try:
                    rows = departments_newest_first(repo.get_all() or [])
                except Exception as err:
                    log.warning("Failed to fetch departments: %s", err)
                    rows = []
                if not rows:
                    UI.empty_state("لا توجد أقسام بعد", "أضف أول قسم.", icon="business")
                    return
                with ui.column().classes("app-dept-list w-full gap-0"):
                    for r in rows:
                        with ui.row().classes("app-dept-row w-full items-center no-wrap gap-3"):
                            with ui.column().classes("flex-1 min-w-0 gap-0"):
                                ui.label(r.get("name_ar") or "—").classes("app-text-primary font-semibold")
                                ui.label(r.get("name_en") or "").classes("app-caption")
                            UI.icon_button("edit", "تعديل القسم", on_click=lambda _e, row=r: _edit(row), dense=True)
                            UI.danger_icon_button("delete", "حذف القسم", on_click=lambda _e, row=r: _delete(row))

            def _edit(row: dict):
                with ui.dialog() as dlg, UI.card().classes("w-[440px] max-w-full gap-4"):
                    UI.card_header(f"تعديل القسم: {row.get('name_ar', '')}", "edit")
                    e_ar = UI.text_input("اسم القسم بالعربية", value=row.get("name_ar") or "")
                    e_en = UI.text_input("اسم القسم بالإنكليزية", value=row.get("name_en") or "")

                    def _save():
                        n_ar = (e_ar.value or "").strip()
                        n_en = (e_en.value or "").strip()
                        if not n_ar or not n_en:
                            ui.notify("اكتب اسم القسم بالعربية والإنكليزية", type="warning")
                            return
                        try:
                            repo.update(dept_id=int(row["id"]), name_ar=n_ar, name_en=n_en)
                            ui.notify("تم تعديل القسم بنجاح", type="positive")
                            dlg.close()
                            dept_list.refresh()
                        except OfflineModeError as err:
                            ui.notify(str(err), type="warning")
                        except Exception as err:
                            log.error("Error saving department: %s", err)
                            ui.notify(f"تعذر الحفظ: {err}", type="negative")

                    with ui.row().classes("app-dialog-actions"):
                        UI.ghost_button("إلغاء", on_click=dlg.close)
                        UI.primary_button("حفظ", icon="save", on_click=_save)
                dlg.open()

            def _delete(row: dict):
                name_ar = row.get("name_ar", "")

                def do_delete():
                    try:
                        repo.delete(row["id"])
                        UI.notify(f"تم حذف القسم ({name_ar})", type="positive")
                        dept_list.refresh()
                    except OfflineModeError as err:
                        UI.notify(str(err), type="warning")
                    except Exception as err:
                        UI.notify(f"تعذر حذف القسم: فيه طلاب أو مواد. {err}", type="negative")

                UI.confirm_dialog(
                    "حذف القسم",
                    f"سيُحذف القسم ({name_ar}). لا يمكن حذفه إذا كان فيه طلاب أو مواد دراسية.",
                    "حذف القسم",
                    do_delete,
                )

            dept_list()
