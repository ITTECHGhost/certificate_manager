import logging
from typing import Callable, Any
from nicegui import ui
from data.repositories import StudyRoutineRepository

log = logging.getLogger(__name__)


def show_apply_routine_dialog(student: dict, on_success_callback: Callable[[], Any] | None = None) -> None:
    """
    Reusable UI dialog to apply a predefined study routine to a student.
    
    Filters available routines by the student's department_id and study_system_id,
    confirms execution, and automatically generates the academic periods and course
    enrollments on success.
    """
    student_id = int(student.get("id") or 0)
    student_name = student.get("full_name_ar") or student.get("name_ar") or "طالب غير محدد"
    dept_id = student.get("department_id")
    dept_name = student.get("dept_name_ar") or student.get("department_name_ar") or (f"قسم #{dept_id}" if dept_id else "قسم غير محدد")
    sys_id = student.get("study_system_id")

    # Fetch and filter routines matching the student's department and study system
    try:
        repo = StudyRoutineRepository()
        all_routines = repo.get_all() or []
    except Exception as exc:
        log.error(f"Failed to fetch routines for student assignment: {exc}")
        all_routines = []

    matching_routines = [
        r for r in all_routines
        if (dept_id is None or int(r.get("department_id") or 0) == int(dept_id or 0) or int(r.get("department_id") or 0) == 0)
        and (sys_id is None or int(r.get("study_system_id") or 0) == int(sys_id or 0) or int(r.get("study_system_id") or 0) == 0)
    ]

    # Fallback 1: all routines matching student's department
    if not matching_routines and dept_id:
        matching_routines = [
            r for r in all_routines
            if int(r.get("department_id") or 0) == int(dept_id or 0) or int(r.get("department_id") or 0) == 0
        ]

    # Fallback 2: all routines in the system
    if not matching_routines:
        matching_routines = all_routines

    routine_options = {}
    for r in matching_routines:
        r_id = r.get("id")
        r_name = r.get("name_ar") or "روتين دراسي"
        c_count = len(r.get("courses") or [])
        d_name = r.get("dept_name_ar") or r.get("department_name_ar") or ""
        badge = f" [{d_name}]" if d_name else ""
        label = f"{r_name}{badge} ({c_count} مواد)" if c_count else f"{r_name}{badge}"
        routine_options[r_id] = label

    init_selection = list(routine_options.keys())[0] if routine_options else None

    # Main Dialog Window
    dialog = ui.dialog()
    with dialog, ui.card().classes("w-full max-w-md p-6 shadow-xl rounded-2xl gap-4 bg-[var(--surface-card)] text-[var(--text-primary)] border border-[var(--border-default)]"):
        # Header
        with ui.row().classes("w-full items-center gap-2 pb-3 border-b border-[var(--border-default)]"):
            ui.icon("auto_mode", size="sm").classes("text-teal-600 dark:text-teal-400 shrink-0")
            with ui.column().classes("gap-0"):
                ui.label("تطبيق روتين دراسي / Apply Study Routine").classes("text-base font-bold text-[var(--text-primary)]")
                ui.label("إسناد خطة دراسية كاملة وتوليد الفصول والمواد تلقائياً").classes("text-xs text-[var(--text-muted)]")

        # Student Information Confirmation Box
        with ui.column().classes("w-full p-3 rounded-xl bg-[var(--surface-main)] border border-[var(--border-default)] gap-1"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("الطالب:").classes("text-xs text-[var(--text-muted)] font-semibold")
                ui.label(student_name).classes("text-xs font-bold text-[var(--text-primary)]")
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("القسم الدراسي:").classes("text-xs text-[var(--text-muted)] font-semibold")
                ui.label(dept_name).classes("text-xs font-medium text-teal-600 dark:text-teal-400")

        # Routine Selection Dropdown / Warning State
        if not matching_routines:
            with ui.row().classes("w-full p-3 items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-300"):
                ui.icon("warning", size="xs").classes("shrink-0 text-amber-500")
                ui.label("لا توجد روتينات دراسية مطابقة لقسم ونظام هذا الطالب.").classes("text-xs font-medium")
            routine_select = None
        else:
            routine_select = ui.select(
                options=routine_options,
                value=init_selection,
                label="الروتين الدراسي المتاح / Available Routine",
                with_input=True
            ).classes("w-full text-sm").props("outlined dense use-input fill-input")

        # Action Buttons
        with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-[var(--border-default)]"):
            ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat").classes("text-[var(--text-muted)] text-sm")

            def handle_apply_click():
                if not routine_select or not routine_select.value:
                    ui.notify("يرجى تحديد روتين دراسي من القائمة", type="warning")
                    return

                selected_routine_id = int(routine_select.value)

                # Confirmation Modal before applying
                confirm_dialog = ui.dialog()
                with confirm_dialog, ui.card().classes("w-full max-w-sm p-5 shadow-2xl rounded-2xl gap-4 bg-[var(--surface-card)] text-[var(--text-primary)] border border-[var(--border-default)]"):
                    with ui.row().classes("items-center gap-2 pb-2 border-b border-[var(--border-default)]"):
                        ui.icon("help_outline", size="sm").classes("text-teal-600 dark:text-teal-400 shrink-0")
                        ui.label("تأكيد تطبيق الخطة الدراسية").classes("text-sm font-bold text-[var(--text-primary)]")

                    ui.label(
                        "هل أنت متأكد من تطبيق هذا الروتين؟ سيتم إضافة المراحل والمواد تلقائياً."
                    ).classes("text-xs text-[var(--text-secondary)] leading-relaxed")

                    with ui.row().classes("w-full justify-end gap-2 pt-2 border-t border-[var(--border-default)]"):
                        ui.button("تراجع", on_click=confirm_dialog.close).props("flat").classes("text-[var(--text-muted)] text-xs")

                        def execute_apply():
                            confirm_dialog.close()
                            try:
                                result = repo.apply_routine_to_student(
                                    student_id=student_id,
                                    routine_id=selected_routine_id
                                ) or {}

                                periods_count = result.get("periods_added") or result.get("periods_affected") or 0
                                courses_count = result.get("courses_added") or result.get("added_courses") or 0

                                ui.notify(
                                    f"تم الإضافة: {periods_count} مرحلة/فصل و {courses_count} مادة",
                                    type="positive"
                                )
                                dialog.close()

                                if on_success_callback and callable(on_success_callback):
                                    on_success_callback()

                            except Exception as err:
                                log.error(f"Error applying study routine {selected_routine_id} to student {student_id}: {err}")
                                ui.notify(f"خطأ أثناء تطبيق الروتين: {err}", type="negative")

                        ui.button("تأكيد التطبيق", icon="check", on_click=execute_apply).classes(
                            "bg-teal-600 hover:bg-teal-700 text-white text-xs px-3 py-1.5 rounded-lg"
                        )

                confirm_dialog.open()

            apply_btn = ui.button(
                "تطبيق / Apply",
                icon="check_circle",
                on_click=handle_apply_click
            ).classes("bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-2 rounded-lg")

            if not matching_routines:
                apply_btn.disable()

    dialog.open()
