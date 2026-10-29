# =============================================================================
# nicegui_screens/settings/appearance.py — Settings: theme, accent, font, RTL
# =============================================================================

from nicegui import ui
from nicegui_ui.ui_components import UI


class AppearanceMixin:
    """Appearance preferences with live preview (part of SettingsScreen)."""

    def _apply_initial_theme(self) -> None:
        """Applies saved theme preference on screen load."""
        self.session.apply_theme_mode()

    def _section_appearance(self) -> None:
        with UI.card():
            UI.card_header("المظهر والسمات — Appearance & Theme", "palette", icon_css="stat-text-purple")

            # Always read from session.preferences — it IS the source of truth after login.
            # The DB load in _load_data() already synced into session.preferences.
            pref = self.session.preferences
            saved_theme = str(pref.get("theme", "Dark")).strip().capitalize()
            if saved_theme not in ("System", "Light", "Dark"):
                saved_theme = "Dark"
            saved_accent = str(pref.get("accent_color", "blue")).lower().replace("_", "-")
            if saved_accent == "dark-blue":
                saved_accent = "blue"
            valid_accents = ["blue", "green", "orange", "purple", "red"]
            if saved_accent not in valid_accents:
                saved_accent = "blue"
            saved_font  = str(pref.get("font_family", "Segoe UI"))
            saved_size  = int(pref.get("font_size_base") or 14)
            saved_rtl   = int(pref.get("is_arabic_rtl", 1))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.theme_select = UI.select(
                    "الوضع (فاتح/داكن) / Theme Mode",
                    options=["System", "Light", "Dark"],
                    value=saved_theme,
                    on_change=self._on_theme_select_change
                )

                self.accent_select = UI.select(
                    "اللون الأساسي / Accent Color",
                    options=valid_accents,
                    value=saved_accent,
                    on_change=self._on_accent_select_change
                )

                self.font_select = UI.select(
                    "نوع الخط / Font Family",
                    options=["Arial", "Segoe UI", "Roboto", "Cairo", "Tahoma", "Noto Sans Arabic", "times new roman"],
                    value=saved_font,
                    on_change=self._on_font_select_change
                )

                self.font_size_input = UI.number_input(
                    "حجم الخط الأساسي / Base Font Size",
                    value=saved_size, min=10, max=24,
                    on_change=self._on_font_size_change
                )

            with ui.row().classes("app-tile w-full items-center justify-between p-3 rounded-xl border"):
                UI.standard_label("اتجاه الواجهة من اليمين إلى اليسار / Arabic RTL Layout")
                self.rtl_switch = UI.switch("تفعيل RTL / Enable RTL", value=bool(saved_rtl), on_change=self._on_rtl_switch_change)

            UI.success_button(
                "حفظ وتطبيق المظهر / Save Appearance",
                icon="brush",
                on_click=self._save_appearance
            ).classes("self-end")

    def _on_theme_select_change(self, e=None) -> None:
        """Live theme switch when Theme Mode dropdown option changes."""
        from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode
        from nicegui_ui.state import log_state
        raw_val = self._get_event_value(e, self.theme_select, "Dark")
        val = str(raw_val or "Dark")
        if val == "Dark":
            set_dark_mode(True)
        elif val == "Light":
            set_dark_mode(False)
        else:
            set_dark_mode(is_windows_dark_mode())

        # Update session memory
        self.session.update_preferences(theme=val)

        # Update database and track result
        mysql_result = "success"
        try:
            self.s_repo.update_user_appearance(
                emp_id=self.emp_id,
                theme=val,
                accent=self.session.accent_color,
                font=str(self.session.preferences.get("font_family") or "Segoe UI"),
                size=int(self.session.preferences.get("font_size_base") or 13),
                rtl=int(self.session.preferences.get("is_arabic_rtl") or 1)
            )
        except Exception as exc:
            mysql_result = f"error: {exc}"

        dark_val = None
        try:
            dark_val = getattr(ui.dark_mode(), 'value', None)
        except Exception:
            pass

        log_state("THEME_TOGGLE", {
            "target_value": val,
            "app_session_preferences": dict(self.session.preferences),
            "ui_dark_mode_value": dark_val,
            "mysql_update_result": mysql_result
        })

        ui.notify(
            f"تم تغيير المظهر إلى {'الداكن' if val == 'Dark' else ('الفاتح' if val == 'Light' else 'النظام')} / Theme set to {val}!",
            type="info"
        )

    def _on_accent_select_change(self, e=None) -> None:
        """Live accent palette switch when Accent Color dropdown option changes."""
        from nicegui_ui.ui_theme import set_accent
        raw_val = self._get_event_value(e, self.accent_select, "blue")
        val = str(raw_val or "blue")
        set_accent(val)
        self.session.update_preferences(accent_color=val)
        ui.notify(f"تم تغيير اللون الأساسي / Accent set to {val}!", type="info")

    def _on_font_select_change(self, e=None) -> None:
        """Live font family switch when Font Family dropdown option changes."""
        from nicegui_ui.ui_theme import set_font_family
        raw_val = self._get_event_value(e, self.font_select, "Segoe UI")
        val = str(raw_val or "Segoe UI")
        set_font_family(val)
        self.session.update_preferences(font_family=val)
        ui.notify(f"تم تغيير نوع الخط إلى {val} / Font family set to {val}!", type="info")

    def _on_font_size_change(self, e=None) -> None:
        """Live base font size scale when Base Font Size number input changes."""
        from nicegui_ui.ui_theme import set_font_size
        try:
            raw_val = self._get_event_value(e, self.font_size_input, 13)
            val = int(raw_val or 13)
            set_font_size(val)
            self.session.update_preferences(font_size_base=val)
        except Exception:
            pass

    def _on_rtl_switch_change(self, e=None) -> None:
        """Live RTL / LTR layout direction switch when RTL toggle is changed."""
        from nicegui_ui.ui_theme import set_rtl
        try:
            raw_val = self._get_event_value(e, self.rtl_switch, True)
            val = bool(raw_val)
            set_rtl(val)
            self.session.update_preferences(is_arabic_rtl=1 if val else 0)
            ui.notify(f"تم تغيير اتجاه الواجهة إلى {'اليمين (RTL)' if val else 'اليسار (LTR)'} / Layout set to {'RTL' if val else 'LTR'}!", type="info")
        except Exception:
            pass

    def _save_appearance(self) -> None:
        from nicegui_ui.state import log_state
        try:
            theme_val = str((self.theme_select.value if self.theme_select else None) or "Dark")
            accent_val = str((self.accent_select.value if self.accent_select else None) or "blue")
            font_val = str((self.font_select.value if self.font_select else None) or "Arial")
            size_val = int((self.font_size_input.value if self.font_size_input else None) or 14)
            rtl_val = 1 if (self.rtl_switch.value if self.rtl_switch else True) else 0

            from nicegui_ui.ui_theme import set_rtl
            set_rtl(bool(rtl_val))

            mysql_result = "success"
            try:
                self.s_repo.update_user_appearance(
                    emp_id=self.emp_id,
                    theme=theme_val,
                    accent=accent_val,
                    font=font_val,
                    size=size_val,
                    rtl=rtl_val
                )
            except Exception as exc:
                mysql_result = f"error: {exc}"

            self.session.update_preferences(
                theme=theme_val,
                accent_color=accent_val,
                font_family=font_val,
                font_size_base=size_val,
                is_arabic_rtl=rtl_val
            )

            log_state("THEME_SAVE", {
                "target_value": theme_val,
                "accent_color": accent_val,
                "font_family": font_val,
                "font_size_base": size_val,
                "app_session_preferences": dict(self.session.preferences),
                "mysql_update_result": mysql_result
            })

            ui.notify("تم حفظ وتطبيق تفضيلات المظهر بنجاح / Appearance saved & applied!", type="positive")
        except Exception as exc:
            ui.notify(f"Error saving appearance: {exc}", type="negative")
