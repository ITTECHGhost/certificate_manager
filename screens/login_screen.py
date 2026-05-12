import os
from PIL import Image
import customtkinter as ctk
from config import AppColors, AppFonts, AppSizes
from data.repositories import PersonnelRepository

class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTk, on_login_success):
        super().__init__(parent, fg_color=AppColors.WINDOW_BG, corner_radius=0)
        self.grid_propagate(False)
        self._on_login_success = on_login_success
        self._show_password = False
        self._build()

    def _build(self):
        # Two-column layout
        self.grid_columnconfigure(0, weight=3) # Left (Logo)
        self.grid_columnconfigure(1, weight=2) # Right (Form)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDE: Logo Area ---
        left_frame = ctk.CTkFrame(self, fg_color=AppColors.WINDOW_BG, corner_radius=0)
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=1)

        # Attempt to load logo
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".gemini", "antigravity", "brain", "3e6478ba-8756-458a-9727-7051750af099", "university_logo_placeholder_1778489708205.png")
        # NOTE: Using a relative path or a more robust way to find the artifact in a real app would be better,
        # but here we use the absolute path for immediate visibility.
        
        try:
            pil_img = Image.open(r"csit.png")
            logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(350, 350))
            logo_label = ctk.CTkLabel(left_frame, image=logo_img, text="")
            logo_label.grid(row=0, column=0)
        except Exception:
            # Fallback if image fails
            ctk.CTkLabel(
                left_frame, 
                text="UNIVERSITY LOGO", 
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=40, weight="bold"),
                text_color=AppColors.TEXT_MUTED
            ).grid(row=0, column=0)

        # --- RIGHT SIDE: Login Card ---
        right_frame = ctk.CTkFrame(self, fg_color=AppColors.HEADER_BG, corner_radius=0)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(right_frame, fg_color=AppColors.CARD_BG, corner_radius=AppSizes.CORNER_RADIUS_CARD, width=400)
        card.grid(row=0, column=0, padx=40, pady=40)
        card.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            card,
            text="تسجيل الدخول  /  Login",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING, weight="bold"),
            text_color=AppColors.NAV_TEXT
        )
        title_label.grid(row=0, column=0, pady=(40, 30), padx=30)

        # Username
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(
            card,
            textvariable=self.username_var,
            placeholder_text="اسم المستخدم  /  Username",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            justify="center",
            height=45
        )
        self.username_entry.grid(row=1, column=0, pady=(0, 15), padx=40, sticky="ew")

        # Password with Eye Button
        self.password_var = ctk.StringVar()
        pass_container = ctk.CTkFrame(card, fg_color="transparent")
        pass_container.grid(row=2, column=0, pady=(0, 20), padx=40, sticky="ew")
        pass_container.grid_columnconfigure(0, weight=1)

        self.password_entry = ctk.CTkEntry(
            pass_container,
            textvariable=self.password_var,
            placeholder_text="كلمة المرور  /  Password",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            show="*",
            justify="center",
            height=45
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")

        self.eye_btn = ctk.CTkButton(
            pass_container,
            text="👁",
            width=40,
            height=45,
            fg_color="gray70",
            hover_color="gray60",
            text_color="white",
            command=self._toggle_password
        )
        self.eye_btn.grid(row=0, column=1, padx=(5, 0))

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
            text="دخول  /  Sign In",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY, weight="bold"),
            height=45,
            command=self._attempt_login
        )
        self.login_btn.grid(row=4, column=0, pady=(0, 40), padx=40, sticky="ew")
        
        # Bind enter key
        self.password_entry.bind("<Return>", lambda e: self._attempt_login())
        self.username_entry.bind("<Return>", lambda e: self._attempt_login())

    def _toggle_password(self):
        self._show_password = not self._show_password
        if self._show_password:
            self.password_entry.configure(show="")
            self.eye_btn.configure(text="🙈")
        else:
            self.password_entry.configure(show="*")
            self.eye_btn.configure(text="👁")

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

        repo = PersonnelRepository()
        user_data = repo.authenticate(username, password)
        if user_data:
            self._on_login_success(user_data)
        else:
            self.error_label.configure(text="اسم المستخدم أو كلمة المرور غير صحيحة")
