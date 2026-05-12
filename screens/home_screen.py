# =============================================================================
# screens/home_screen.py — Dashboard / Home Screen
# =============================================================================
#
# CHANGES:
#   - Removed make_divider() call that caused a visual glitch line
#   - Uses padding between sections instead of a drawn divider
#
# =============================================================================

import customtkinter as ctk
from config import AppFonts, AppColors, AppSizes, HOME_STAT_CARDS, HOME_QUICK_ACTIONS
from data.repositories import BaseRepository
from ui.base_screen import BaseScreen
from ui.widgets import make_stat_card, make_quick_action_button


class HomeScreen(BaseScreen):
    """
    Dashboard screen shown on application startup.

    Layout (top to bottom):
        1. Bilingual welcome heading
        2. Row of 4 stat cards
        3. Quick Actions heading
        4. Row of 3 quick-action buttons
    """

    def __init__(self, parent: ctk.CTkFrame, switch_callback) -> None:
        self._stat_labels: dict[str, ctk.CTkLabel] = {}
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._build_welcome(scroll)
        self._build_stat_cards(scroll)
        self._build_quick_actions(scroll)

    def _build_welcome(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            parent,
            text="أهلاً بك في نظام إدارة الشهادات",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TITLE, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", pady=(0, 4))

        ctk.CTkLabel(
            parent,
            text="Welcome to the Certificate Management System",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
            text_color=AppColors.TEXT_MUTED,
            anchor="e",
        ).grid(row=1, column=0, sticky="e", pady=(0, 24))

    def _build_stat_cards(self, parent: ctk.CTkFrame) -> None:
        cards_frame = ctk.CTkFrame(parent, fg_color="transparent")
        cards_frame.grid(row=2, column=0, sticky="ew", pady=(0, 28))

        for i in range(len(HOME_STAT_CARDS)):
            cards_frame.grid_columnconfigure(i, weight=1, uniform="card")

        for col, cfg in enumerate(HOME_STAT_CARDS):
            card = make_stat_card(
                parent=cards_frame,
                icon=cfg["icon"],
                label_ar=cfg["ar"],
                label_en=cfg["en"],
                accent_color=cfg["color"],
            )
            card.grid(row=0, column=col, padx=6, sticky="nsew")
            self._stat_labels[cfg["db_table"]] = card.count_label

    def _build_quick_actions(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            parent,
            text="إجراءات سريعة  —  Quick Actions",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING, weight="bold"),
            anchor="e",
        ).grid(row=4, column=0, sticky="e", pady=(0, 10))

        actions_frame = ctk.CTkFrame(parent, fg_color="transparent")
        actions_frame.grid(row=5, column=0, sticky="ew")

        for i in range(len(HOME_QUICK_ACTIONS)):
            actions_frame.grid_columnconfigure(i, weight=1, uniform="action")

        for col, action in enumerate(HOME_QUICK_ACTIONS):
            make_quick_action_button(
                parent=actions_frame,
                text_ar=action["ar"],
                text_en=action["en"],
                command=lambda t=action["target"]: self.navigate(t),
            ).grid(row=0, column=col, padx=6, sticky="ew")

    def refresh(self) -> None:
        for cfg in HOME_STAT_CARDS:
            label = self._stat_labels.get(cfg["db_table"])
            if not label:
                continue
            try:
                repo = BaseRepository()
                count = repo.count_table_rows(cfg["db_table"], cfg.get("filter", ""))
                label.configure(text=str(count))
            except Exception:
                label.configure(text="!")
