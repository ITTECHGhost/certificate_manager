# =============================================================================
# screens/placeholder_screen.py — Under Construction Placeholder
# =============================================================================
#
# WHAT THIS SCREEN DOES:
#   Displayed for screens that have not been built yet.
#   Replaced one by one in later development steps.
#
# =============================================================================

import customtkinter as ctk
from config import AppFonts, AppColors
from ui.base_screen import BaseScreen


class PlaceholderScreen(BaseScreen):
    """
    Temporary placeholder for screens not yet implemented.
    Shows the screen name and an under-construction message.

    Usage:
        screen = PlaceholderScreen(parent, callback, "الطلاب", "Students")
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        switch_callback,
        name_ar: str,
        name_en: str,
    ) -> None:
        # Store names before _build() is called by super().__init__
        self._name_ar = name_ar
        self._name_en = name_en
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        """Build a centred under-construction message."""
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            center,
            text="🚧",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            center,
            text=self._name_ar,
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_TITLE,
                weight="bold",
            ),
        ).pack()

        ctk.CTkLabel(
            center,
            text=self._name_en,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            text_color=AppColors.TEXT_MUTED,
        ).pack(pady=(2, 12))

        ctk.CTkLabel(
            center,
            text="هذه الصفحة قيد الإنشاء  —  This screen is under construction",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            text_color=AppColors.TEXT_MUTED,
        ).pack()

    def refresh(self) -> None:
        """Nothing to refresh on a placeholder screen."""
        pass
