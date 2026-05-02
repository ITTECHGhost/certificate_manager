import customtkinter as ctk
from config import AppColors, AppFonts, AppSizes
from data.queries import authenticate_user

class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTk, on_login_success):
        super().__init__(parent, fg_color=AppColors.WINDOW_BG, corner_radius=0)
        self.grid_propagate(False)
        self._on_login_success = on_login_success
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Center card
        card = ctk.CTkFrame(self, fg_color=AppColors.CARD_BG, corner_radius=AppSizes.CORNER_RADIUS_CARD, width=400)
        card.grid(row=0, column=0)
        
        # Grid inside card
        card.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            card,
            text="تسجيل الدخول",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING, weight="bold"),
            text_color=AppColors.NAV_TEXT
        )
        title_label.grid(row=0, column=0, pady=(30, 20), padx=30)

        # Username
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            card,
            textvariable=self.username_var,
            placeholder_text="اسم المستخدم",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            justify="center",
            height=40
        )
        self.username_entry.grid(row=1, column=0, pady=(0, 15), padx=40, sticky="ew")

        # Password
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            card,
            textvariable=self.password_var,
            placeholder_text="كلمة المرور",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            show="*",
            justify="center",
            height=40
        )
        self.password_entry.grid(row=2, column=0, pady=(0, 20), padx=40, sticky="ew")

        # Error message
        self.error_label = ctk.CTkLabel(
            card,
            text="",
            text_color="red",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY)
        )
        self.error_label.grid(row=3, column=0, pady=(0, 10))

        # Login button
        self.login_btn = ctk.CTkButton(
            card,
            text="دخول",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY, weight="bold"),
            height=40,
            command=self._attempt_login
        )
        self.login_btn.grid(row=4, column=0, pady=(0, 30), padx=40, sticky="ew")
        
        # Bind enter key
        self.password_entry.bind("<Return>", lambda e: self._attempt_login())
        self.username_entry.bind("<Return>", lambda e: self._attempt_login())

    def _attempt_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            self.error_label.configure(text="يرجى إدخال اسم المستخدم وكلمة المرور")
            return

        # Hardcoded fallback for testing as requested
        if username == "1" and password == "1":
            user_data = {"id": 1, "username": "1", "role": "admin", "name_ar": "مدير النظام (مؤقت)"}
            self._on_login_success(user_data)
            return

        user_data = authenticate_user(username, password)
        if user_data:
            self._on_login_success(user_data)
        else:
            self.error_label.configure(text="اسم المستخدم أو كلمة المرور غير صحيحة")
