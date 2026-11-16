"""Fields do not keep old values: upload boxes empty themselves when done, and the
report forms clear after a successful export; «مسح الكل» clears every filter."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeUpload:
    def __init__(self):
        self.handlers, self.was_reset = {}, False

    def on(self, event, handler):
        self.handlers[event] = handler
        return self

    def reset(self):
        self.was_reset = True


def test_clear_when_done_resets_on_finish():
    from nicegui_ui.upload_utils import clear_when_done
    up = _FakeUpload()
    assert clear_when_done(up) is up
    assert not up.was_reset
    up.handlers["finish"](None)
    assert up.was_reset


def test_every_upload_box_clears_itself():
    """No screen builds a ui.upload that is not wrapped in clear_when_done."""
    bare = []
    for folder in ("nicegui_screens", "nicegui_ui"):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, folder)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                for m in re.finditer(r"ui\.upload\(", text):
                    if not text[max(0, m.start() - 16):m.start()].endswith("clear_when_done("):
                        bare.append(f"{os.path.relpath(path, ROOT)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert bare == []


class _Sel:
    def __init__(self, value):
        self.value = value

    def set_value(self, v):
        self.value = v


def test_reports_clear_filters():
    from nicegui_screens.reports_screen import ReportsScreen
    scr = ReportsScreen.__new__(ReportsScreen)
    for attr, val in (("f_dept", 3), ("f_sys", 2), ("f_year", 2025), ("f_adm", 2020), ("f_gender", 1),
                      ("f_type", "evening"), ("f_status", "graduated"), ("f_sem", "first"),
                      ("f_nat", "iraqi"), ("f_then", "gender"), ("f_name", "علي"), ("f_group", "gender")):
        setattr(scr, attr, _Sel(val))
    ran = []
    scr._run = lambda: ran.append(True)
    scr.clear_filters()
    assert scr._filters() == {"department_id": 0, "study_system_id": 0, "study_type": "", "status": "",
                              "graduation_year": 0, "semester": "", "admission_year": 0, "gender": 0,
                              "nationality": "", "name": ""}
    assert scr.f_group.value == "department" and scr.f_then.value == "" and ran == [True]


def test_students_clear_filters():
    from nicegui_screens.students_screen import EMPTY_FILTERS, StudentsScreen
    scr = StudentsScreen.__new__(StudentsScreen)
    scr.filters = {**EMPTY_FILTERS, "study_type": "evening", "status": "graduated"}
    scr._filter_inputs = {"study_type": _Sel("evening"), "status": _Sel("graduated")}
    scr.search_input = _Sel("علي")
    searched = []
    scr.perform_search = lambda reset_offset=False: searched.append(reset_offset)
    scr.clear_filters()
    assert scr.filters == EMPTY_FILTERS
    assert all(s.value is None for s in scr._filter_inputs.values())
    assert scr.search_input.value == "" and searched == [True]
