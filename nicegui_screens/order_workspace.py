# =============================================================================
# nicegui_screens/order_workspace.py — the working part of one graduation order:
#   top:    count check + auto-link (with undo) + collapsible "add students" panel
#   bottom: scanned order pages (left) | linked students (right), side by side
# =============================================================================

import base64
import logging

from nicegui import run, ui

from nicegui_ui.ui_components import UI
from nicegui_ui.upload_utils import read_upload

log = logging.getLogger(__name__)

SEMESTER_AR = {"first": "الأول", "second": "الثاني", "summer": "الصيفي"}


class OrderWorkspaceMixin:
    """Part of GraduationOrdersScreen (needs self.student_repo)."""

    def _build_order_workspace(self, oid: int, order: dict) -> None:
        state = {"undo_ids": [], "name": "", "matching_only": True}
        expected = order.get("num_students")
        try:
            expected = int(expected) if expected not in (None, "") else None
        except (TypeError, ValueError):
            expected = None

        def refresh_all():
            count_bar.refresh()
            linked_panel.refresh()
            candidates_panel.refresh()

        # ── Count check + auto-link ───────────────────────────────────────────
        @ui.refreshable
        def count_bar():
            try:
                linked = len(self.student_repo.get_by_order(oid) or [])
            except Exception:
                linked = 0
            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                ui.icon("groups", size="sm").classes("app-text-accent")
                if expected is None:
                    ui.label(f"المرتبطون: {linked}").classes("font-bold app-text-primary")
                    ui.label("(لم يُكتب عدد الطلاب في الأمر)").classes("app-caption")
                else:
                    ok = linked == expected
                    ui.label(f"المرتبطون: {linked} من {expected} في الأمر").classes(
                        "font-bold " + ("text-emerald-500" if ok else "text-amber-500"))
                    if not ok:
                        diff = expected - linked
                        ui.label(f"ينقص {diff}" if diff > 0 else f"يزيد {-diff}").classes(
                            "app-chip app-chip--warning")
                ui.space()
                if state["undo_ids"]:
                    UI.secondary_button(f"تراجع عن آخر ربط ({len(state['undo_ids'])})", icon="undo",
                                        on_click=undo_last)
                UI.primary_button("ربط المطابقين تلقائيًا", icon="link", on_click=auto_link)

        def auto_link():
            try:
                count, ids = self.student_repo.auto_link_matching(oid, order)
            except Exception as err:
                ui.notify(f"تعذر الربط التلقائي: {err}", type="negative")
                return
            state["undo_ids"] = ids
            if count:
                ui.notify(f"تم ربط {count} طالب. راجع القائمة واحذف من ليس في الأمر.", type="positive")
            else:
                ui.notify("لا يوجد طلاب مطابقون غير مرتبطين بأمر آخر. تأكد من سنة التخرج المتوقعة للطلاب.",
                          type="info", timeout=8000)
            refresh_all()

        def undo_last():
            try:
                n = self.student_repo.undo_link(oid, state["undo_ids"])
                ui.notify(f"تم إلغاء ربط {n} طالب", type="positive")
            except Exception as err:
                ui.notify(f"تعذر التراجع: {err}", type="negative")
                return
            state["undo_ids"] = []
            refresh_all()

        with UI.card().classes("w-full p-4 gap-3"):
            count_bar()

            # ── Add students (collapsible) ───────────────────────────────────
            with ui.expansion("إضافة طلاب إلى الأمر", icon="person_add").classes("w-full"):
                with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                    def on_name(e):
                        state["name"] = str(e.value or "").strip()
                        candidates_panel.refresh()

                    def on_match(e):
                        state["matching_only"] = bool(e.value)
                        candidates_panel.refresh()

                    UI.text_input("", placeholder="بحث بالاسم...", on_change=on_name).classes("flex-1 min-w-[200px]")
                    ui.switch("المطابقون للأمر فقط (القسم، النظام، سنة وفصل التخرج)", value=True,
                              on_change=on_match)

                @ui.refreshable
                def candidates_panel():
                    try:
                        rows = self.student_repo.candidates_for_order(
                            oid, state["name"], state["matching_only"], limit=200) or []
                    except Exception as err:
                        log.warning(f"candidates_for_order failed: {err}")
                        ui.label(f"تعذر جلب الطلاب: {err}").classes("app-caption")
                        return
                    if not rows:
                        ui.label("لا يوجد طلاب غير مرتبطين بهذا الوصف").classes("app-caption py-4")
                        return
                    with ui.row().classes("w-full items-center"):
                        ui.label(f"{len(rows)} طالب").classes("app-caption")
                        ui.space()

                        def link_all(ids=[r["id"] for r in rows]):
                            done = []
                            for sid in ids:
                                try:
                                    self.student_repo.link_to_order(sid, oid)
                                    done.append(sid)
                                except Exception as err:
                                    log.warning(f"link {sid} failed: {err}")
                            state["undo_ids"] = done
                            ui.notify(f"تم ربط {len(done)} طالب", type="positive")
                            refresh_all()

                        UI.secondary_button("ربط كل المعروضين", icon="playlist_add", on_click=link_all)
                    with ui.column().classes("w-full gap-1 max-h-[300px] overflow-y-auto"):
                        for st in rows:
                            with ui.row().classes("w-full items-center gap-2 p-2 rounded-lg border border-[var(--border-default)]"):
                                with ui.column().classes("flex-1 min-w-0 gap-0"):
                                    ui.label(st.get("full_name_ar") or "—").classes("font-bold text-sm truncate")
                                    sem = SEMESTER_AR.get(str(st.get("expected_graduation_semester") or ""), "")
                                    yr = st.get("expected_graduation_year") or "—"
                                    ui.label(f"{st.get('dept_name_ar') or ''} • التخرج المتوقع: {yr} {sem}").classes("app-caption")

                                def link_one(sid=st["id"]):
                                    try:
                                        self.student_repo.link_to_order(sid, oid)
                                        state["undo_ids"] = [sid]
                                        refresh_all()
                                    except Exception as err:
                                        ui.notify(f"تعذر الربط: {err}", type="negative")

                                UI.icon_button("add_link", "ربط بهذا الأمر", on_click=link_one)

                candidates_panel()

        # ── Scanned order | linked students ──────────────────────────────────
        with ui.row().classes("w-full gap-4 items-start no-wrap max-lg:flex-wrap"):
            with UI.card().classes("flex-1 min-w-[320px] p-4 gap-3"):
                self._build_order_images(oid, order)

            with UI.card().classes("flex-1 min-w-[320px] p-4 gap-3"):
                @ui.refreshable
                def linked_panel():
                    try:
                        linked = self.student_repo.get_by_order(oid) or []
                    except Exception as err:
                        log.warning(f"get_by_order failed: {err}")
                        linked = []
                    ui.label(f"الطلاب المرتبطون ({len(linked)})").classes("app-section-title")
                    if not linked:
                        UI.muted_label("لا يوجد طلاب مرتبطون بهذا الأمر")
                        return
                    with ui.column().classes("w-full gap-1 max-h-[640px] overflow-y-auto"):
                        for i, st in enumerate(sorted(linked, key=lambda s: s.get("full_name_ar") or ""), start=1):
                            avg = st.get("average")
                            with ui.row().classes("w-full items-center gap-2 p-2 rounded-lg border border-[var(--border-default)]"):
                                ui.label(str(i)).classes("app-caption w-6 text-center")
                                with ui.column().classes("flex-1 min-w-0 gap-0"):
                                    ui.label(st.get("full_name_ar") or "—").classes("font-bold text-sm truncate")
                                    ui.label(f"المعدل: {float(avg):.2f}" if avg is not None else "المعدل: —").classes("app-caption")

                                def unlink(sid=st["id"]):
                                    try:
                                        self.student_repo.unlink_from_order(sid)
                                        refresh_all()
                                    except Exception as err:
                                        ui.notify(f"تعذر فك الربط: {err}", type="negative")

                                UI.danger_icon_button("link_off", "إلغاء الربط", on_click=unlink)

                linked_panel()

    # ── Scanned order viewer ──────────────────────────────────────────────────
    def _build_order_images(self, oid: int, order: dict) -> None:
        import services.order_images as oi
        view = {"items": [], "i": 0, "zoom": 1.0}

        def load():
            try:
                view["items"] = oi.list_images(oid)
            except Exception as err:
                log.warning(f"list_images failed: {err}")
                view["items"] = []
            view["i"] = min(view["i"], max(0, len(view["items"]) - 1))

        def data_url(item, thumb=False) -> str:
            return "data:image/jpeg;base64," + base64.b64encode(oi.get_image(oid, item, thumb)).decode()

        @ui.refreshable
        def viewer():
            items = view["items"]
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("صور أمر التخرج").classes("app-section-title")
                ui.space()
                if items:
                    ui.label(f"صفحة {view['i'] + 1} من {len(items)}").classes("app-caption")
            if not items:
                UI.muted_label("لا توجد صور بعد. اسحب صور الأمر أو ملف PDF إلى المربع أدناه.")
                return
            item = items[view["i"]]
            rot = int(item.get("rotation") or 0)
            with ui.element("div").classes("w-full overflow-auto rounded-lg border border-[var(--border-default)] bg-white") \
                    .style("height: 560px"):
                try:
                    ui.image(data_url(item)).style(
                        f"width: {int(view['zoom'] * 100)}%; transform: rotate({rot}deg); transform-origin: center;"
                        " transition: transform .2s")
                except Exception as err:
                    ui.label(f"تعذر عرض الصفحة: {err}").classes("app-caption p-4")
            with ui.row().classes("w-full items-center justify-center gap-1"):
                UI.icon_button("chevron_right", "الصفحة السابقة", on_click=lambda: go(-1))
                UI.icon_button("chevron_left", "الصفحة التالية", on_click=lambda: go(1))
                UI.icon_button("zoom_in", "تكبير", on_click=lambda: zoom(0.25))
                UI.icon_button("zoom_out", "تصغير", on_click=lambda: zoom(-0.25))
                UI.icon_button("rotate_left", "تدوير", on_click=lambda: rotate(item, -90))
                UI.icon_button("rotate_right", "تدوير", on_click=lambda: rotate(item, 90))
                UI.icon_button("picture_as_pdf", "تنزيل كـ PDF", on_click=download_pdf)
                UI.danger_icon_button("delete", "حذف هذه الصفحة", on_click=lambda: confirm_delete(item))
            if len(items) > 1:
                with ui.row().classes("w-full gap-2 no-wrap overflow-x-auto py-1"):
                    for n, it in enumerate(items):
                        sel = "border-2 border-[var(--color-accent)]" if n == view["i"] else "border border-[var(--border-default)]"
                        try:
                            ui.image(data_url(it, thumb=True)).classes(f"w-16 h-20 shrink-0 cursor-pointer rounded {sel}") \
                                .props("fit=cover").on("click", lambda _e, k=n: select(k))
                        except Exception:
                            pass

        def go(step: int):
            if view["items"]:
                view["i"] = (view["i"] + step) % len(view["items"])
                viewer.refresh()

        def select(k: int):
            view["i"] = k
            viewer.refresh()

        def zoom(d: float):
            view["zoom"] = min(3.0, max(0.5, view["zoom"] + d))
            viewer.refresh()

        def rotate(item: dict, d: int):
            item["rotation"] = (int(item.get("rotation") or 0) + d) % 360
            viewer.refresh()
            try:
                oi.set_rotation(oid, item["id"], item["rotation"])
            except Exception as err:
                ui.notify(f"لم يُحفظ التدوير: {err}", type="warning")

        def confirm_delete(item: dict):
            def _do():
                try:
                    oi.delete_image(oid, item["id"])
                except Exception as err:
                    ui.notify(f"تعذر الحذف: {err}", type="negative")
                    return
                load()
                viewer.refresh()
            UI.confirm_dialog("حذف صفحة", "ستُحذف هذه الصفحة من أرشيف الأمر على الخادم.", "حذف", _do)

        async def download_pdf():
            try:
                pdf = await run.io_bound(oi.build_pdf, oid, view["items"])
            except Exception as err:
                ui.notify(f"تعذر إنشاء PDF: {err}", type="negative")
                return
            from utils.file_delivery import deliver_file
            safe = str(order.get("order_number") or oid).replace("/", "-").replace("\\", "-")
            deliver_file(pdf, filename=f"امر تخرج {safe}.pdf", title="تم حفظ صور الأمر كملف PDF")

        async def on_upload(e):
            try:
                name, content = await read_upload(e)
            except Exception as err:
                ui.notify(f"تعذر قراءة الملف: {err}", type="negative")
                return
            n = ui.notification(f"جاري تجهيز {name} ورفعه...", spinner=True, timeout=None)
            try:
                added = await run.io_bound(oi.upload_file, oid, name, content)
                ui.notify(f"أضيفت {added} صفحة" if added else "الصفحات موجودة مسبقاً", type="positive")
            except Exception as err:
                ui.notify(f"تعذر رفع {name}: {err}", type="negative")
            finally:
                n.dismiss()
            load()
            view["i"] = max(0, len(view["items"]) - 1)
            viewer.refresh()

        load()
        viewer()
        ui.upload(label="اسحب صور الأمر أو ملف PDF هنا، أو اضغط للاختيار", multiple=True, auto_upload=True,
                  on_upload=on_upload) \
            .props('accept="image/*,.pdf"') \
            .classes("w-full border-2 border-dashed border-[var(--border-default)] rounded-xl")
