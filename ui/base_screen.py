# =============================================================================
# ui/base_screen.py — Abstract Base Screen
# =============================================================================
#
# PURPOSE:
#   Every screen in the application inherits from BaseScreen.
#   It enforces a consistent structure and provides shared functionality
#   so screen authors only write what is unique to their screen.
#
# CONTRACT FOR SUBCLASSES:
#   1. Call super().__init__(parent, switch_callback) in __init__
#   2. Implement _build(self) → construct all widgets for this screen
#   3. Implement refresh(self) → reload fresh data from the DB
#      (called automatically every time this screen becomes active)
#
# WHAT THIS BASE CLASS PROVIDES:
#   • Grid layout with a pre-configured root frame
#   • show_error(message)   → display an error dialog
#   • show_success(message) → display a success dialog
#   • navigate(screen_key)  → switch to another screen
#
# =============================================================================

import customtkinter as ctk
from abc import ABC, abstractmethod


class BaseScreen(ctk.CTkFrame, ABC):
    """
    Abstract base class for all application screens.

    Every screen is a CTkFrame that fills its parent (the screen slot
    in main.py). Screens are created once at startup, then shown/hidden
    by raising/lowering the frame in the Z-order.

    Subclass template:
    ------------------
        class MyScreen(BaseScreen):

            def __init__(self, parent, switch_callback):
                super().__init__(parent, switch_callback)

            def _build(self) -> None:
                # Create all widgets here
                ctk.CTkLabel(self, text="Hello").pack()

            def refresh(self) -> None:
                # Called every time this screen becomes visible
                # Reload data from the DB here
                pass
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        switch_callback,          # Callable[[str], None]
    ) -> None:
        """
        Args:
            parent:          The parent frame (the screen slot in main.py).
            switch_callback: Function to call to navigate to another screen.
                             Usage: self.navigate("students")
        """
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._switch = switch_callback
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build()

    # -------------------------------------------------------------------------
    # Abstract methods — subclasses MUST implement these
    # -------------------------------------------------------------------------

    @abstractmethod
    def _build(self) -> None:
        """
        Construct all widgets for this screen.
        Called once during __init__. Do not call manually.
        """

    @abstractmethod
    def refresh(self) -> None:
        """
        Reload data from the database and update the screen's widgets.
        Called automatically every time this screen becomes the active view.
        """

    # -------------------------------------------------------------------------
    # Navigation helper
    # -------------------------------------------------------------------------

    def navigate(self, screen_key: str) -> None:
        """
        Navigate to another screen by its key.

        Args:
            screen_key: One of the keys defined in config.NAV_ITEMS,
                        e.g. "students", "certificate", "home"

        Example:
            self.navigate("home")
        """
        self._switch(screen_key)

    # -------------------------------------------------------------------------
    # Dialog helpers
    # -------------------------------------------------------------------------

    def show_error(self, message: str, title: str = "خطأ  —  Error") -> None:
        """
        Display a modal error dialog with the given message.

        Args:
            message: The error message to display (Arabic or English).
            title:   Dialog window title. Defaults to bilingual "Error".
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x180")
        dialog.resizable(False, False)
        dialog.grab_set()                   # make it modal
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="❌",
            font=ctk.CTkFont(size=32),
        ).grid(row=0, column=0, pady=(20, 6))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family="Arial", size=13),
            wraplength=360,
            justify="center",
        ).grid(row=1, column=0, padx=20)

        ctk.CTkButton(
            dialog,
            text="حسناً  /  OK",
            width=120,
            command=dialog.destroy,
        ).grid(row=2, column=0, pady=16)

    def show_success(self, message: str, title: str = "نجاح  —  Success") -> None:
        """
        Display a modal success dialog with the given message.

        Args:
            message: The success message to display.
            title:   Dialog window title. Defaults to bilingual "Success".
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x180")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="✅",
            font=ctk.CTkFont(size=32),
        ).grid(row=0, column=0, pady=(20, 6))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family="Arial", size=13),
            wraplength=360,
            justify="center",
        ).grid(row=1, column=0, padx=20)

        ctk.CTkButton(
            dialog,
            text="حسناً  /  OK",
            width=120,
            command=dialog.destroy,
        ).grid(row=2, column=0, pady=16)

    def show_info(self, message: str, title: str = "معلومات  —  Information") -> None:
        """
        Display a modal info dialog with the given message.

        Args:
            message: The information message to display.
            title:   Dialog window title. Defaults to bilingual "Information".
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x180")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="ℹ️",
            font=ctk.CTkFont(size=32),
        ).grid(row=0, column=0, pady=(20, 6))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family="Arial", size=13),
            wraplength=360,
            justify="center",
        ).grid(row=1, column=0, padx=20)

        ctk.CTkButton(
            dialog,
            text="حسناً  /  OK",
            width=120,
            command=dialog.destroy,
        ).grid(row=2, column=0, pady=16)

    def show_confirm(
        self,
        message: str,
        on_confirm,                          # Callable[[], None]
        title: str = "تأكيد  —  Confirm",
    ) -> None:
        """
        Display a modal confirmation dialog with Yes/No buttons.

        Args:
            message:    The question to display.
            on_confirm: Function to call if the user clicks Yes.
            title:      Dialog window title.

        Example:
            self.show_confirm(
                "هل تريد حذف هذا القسم؟  Delete this department?",
                on_confirm=lambda: self._delete(dept_id)
            )
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("440x200")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="⚠️",
            font=ctk.CTkFont(size=32),
        ).grid(row=0, column=0, pady=(20, 6))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family="Arial", size=13),
            wraplength=380,
            justify="center",
        ).grid(row=1, column=0, padx=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=16)

        def _on_yes() -> None:
            dialog.destroy()
            on_confirm()

        ctk.CTkButton(
            btn_frame,
            text="نعم  /  Yes",
            width=110,
            fg_color="#F44336",
            hover_color="#D32F2F",
            command=_on_yes,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame,
            text="لا  /  No",
            width=110,
            fg_color="gray60",
            hover_color="gray50",
            command=dialog.destroy,
        ).pack(side="left", padx=8)
