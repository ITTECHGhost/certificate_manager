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
            UI.card_header("المظهر", "palette")

            # Always read from session.preferences — it IS the source of truth after login.
            # The DB load in _load_data() already synced into session.preferences.
            pref = self.session.preferences
            saved_theme = str(pref.get("theme", "Dark")).strip().capitalize()
            if saved_theme not in ("System", "Light", "Dark"):
                saved_theme = "Dark"
            saved_size  = int(pref.get("font_size_base") or 14)
            saved_rtl   = int(pref.get("is_arabic_rtl", 1))

            # One font stack comes from theme.css; the accent is one of five token sets (theme.css 1b).
            self.font_select = None
            with ui.grid(columns=2).classes("w-full gap-4"):
                self.theme_select = UI.select(
                    "الوضع",
                    options={"System": "حسب النظام", "Light": "فاتح", "Dark": "داكن"},
                    value=saved_theme,
                    on_change=self._on_theme_select_change
                )

                self.font_size_input = UI.number_input(
                    "حجم الخط",
                    value=max(saved_size, 14), min=14, max=18,
                    on_change=self._on_font_size_change
                )

            self._build_accent_picker()

            # Interface language: a setting of this PC (config/ui_language.json)
            from nicegui_ui.i18n import LANGUAGES, get_language
            self.language_select = UI.select(
                "لغة الواجهة", options=dict(LANGUAGES), value=get_language(),
                on_change=self._on_language_change,
            ).classes("max-w-xs")

            # Advanced: the app is Arabic-first; turning RTL off flips every page to LTR
            with ui.expansion("متقدم", icon="tune").classes("w-full"):
                with ui.row().classes("w-full items-center justify-between py-2"):
                    UI.standard_label("اتجاه الواجهة من اليمين إلى اليسار")
                    self.rtl_switch = UI.switch("", value=bool(saved_rtl), on_change=self._on_rtl_switch_change)

            UI.primary_button("حفظ", icon="save", on_click=self._save_appearance).classes("self-end")

    def _build_accent_picker(self) -> None:
        """Colour swatches, one per accent; clicking one recolours the app at once."""
        from nicegui_ui.ui_theme import ACCENT_OPTIONS, ACCENT_LABELS, ACCENT_SWATCHES, normalize_accent
        current = normalize_accent(self.session.preferences.get("accent_color"))
        self._accent_value = current
        self._accent_swatches = {}
        UI.section_label("لون السمة")
        with ui.row().classes("app-accent-picker w-full gap-2 flex-wrap"):
            for name in ACCENT_OPTIONS:
                label = ACCENT_LABELS[name]["ar"]
                btn = ui.button(on_click=lambda _e, n=name: self._on_accent_select_change(n)).props("flat no-caps").classes(
                    "app-accent-option" + (" app-accent-option--active" if name == current else "")
                )
                btn.props(f'aria-label="{label}"')
                with btn:
                    ui.element("span").classes("app-accent-swatch").style(f"background:{ACCENT_SWATCHES[name]}")
                    ui.label(label).classes("app-accent-name")
                self._accent_swatches[name] = btn
        # Kept for code that still reads the old select's value
        self.accent_select = None

    def _on_language_change(self, e=None) -> None:
        """Switch the interface language; the page reloads so every label is rebuilt in it."""
        from nicegui_ui.i18n import set_language, get_language, LANGUAGES
        val = str(self._get_event_value(e, self.language_select, "ar") or "ar")
        if val == get_language():
            return
        set_language(val)
        ui.notify(f"لغة الواجهة: {LANGUAGES[val]}", type="info")   # sent through the table in the new language
        ui.timer(0.6, lambda: ui.navigate.reload(), once=True)

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
            f"تم تغيير المظهر إلى {'الداكن' if val == 'Dark' else ('الفاتح' if val == 'Light' else 'النظام')}",
            type="info"
        )

    def _on_accent_select_change(self, e=None) -> None:
        """Live accent switch from a swatch click (a name) or an event carrying the value."""
        from nicegui_ui.ui_theme import set_accent, normalize_accent, ACCENT_LABELS
        raw_val = e if isinstance(e, str) else self._get_event_value(e, self.accent_select, "green")
        val = normalize_accent(raw_val)
        set_accent(val)
        self._accent_value = val
        for name, btn in getattr(self, "_accent_swatches", {}).items():
            if name == val:
                btn.classes(add="app-accent-option--active")
            else:
                btn.classes(remove="app-accent-option--active")
        self.session.update_preferences(accent_color=val)
        ui.notify(f"لون السمة: {ACCENT_LABELS[val]['ar']}", type="info")

    def _on_font_select_change(self, e=None) -> None:
        """Live font family switch when Font Family dropdown option changes."""
        from nicegui_ui.ui_theme import set_font_family
        raw_val = self._get_event_value(e, self.font_select, "Segoe UI")
        val = str(raw_val or "Segoe UI")
        set_font_family(val)
        self.session.update_preferences(font_family=val)
        ui.notify(f"تم تغيير نوع الخط إلى {val}", type="info")

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
            ui.notify(f"تم تغيير اتجاه الواجهة إلى {"اليمين" if val else "اليسار"}", type="info")
        except Exception:
            pass

    def _save_appearance(self) -> None:
        from nicegui_ui.state import log_state
        try:
            theme_val = str((self.theme_select.value if self.theme_select else None) or "Dark")
            # The font is fixed by the theme; the accent is the swatch picked above
            from nicegui_ui.ui_theme import normalize_accent
            accent_val = normalize_accent(getattr(self, "_accent_value", None) or self.session.preferences.get("accent_color"))
            font_val = str(self.session.preferences.get("font_family") or "Segoe UI")
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

            ui.notify("تم حفظ وتطبيق تفضيلات المظهر بنجاح", type="positive")
        except Exception as exc:
            ui.notify(f"تعذر حفظ إعدادات المظهر: {exc}", type="negative")
