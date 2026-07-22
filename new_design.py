import customtkinter as ctk

# =============================================================================
# THEME CONSTANTS (Simulating the deep slate & emerald dark theme)
# =============================================================================
BG_MAIN = "#0F111A"
BG_CARD = "#1A1D24"
BG_INNER = "#222630"
ACCENT_EMERALD = "#10B981"
ACCENT_EMERALD_HOVER = "#059669"
ACCENT_BLUE = "#3B82F6"
ACCENT_BLUE_HOVER = "#2563EB"
TEXT_MAIN = "#F9FAFB"
TEXT_MUTED = "#9CA3AF"
FONT_FAMILY = "Segoe UI"

# =============================================================================
# INLINE ACADEMIC CARD (The Swappable Component)
# =============================================================================
class InlineAcademicCard(ctk.CTkFrame):
    def __init__(self, master, period_title, enrollments, **kwargs):
        super().__init__(
            master, 
            fg_color=BG_CARD, 
            corner_radius=12, 
            border_width=1, 
            border_color="#2A2D35", 
            **kwargs
        )
        self.period_title = period_title
        self.enrollments = enrollments  # List of dicts: {"id": 1, "name": "...", "score": 85}
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_view_mode()
        self._build_edit_mode()
        
        # Start in view mode
        self.show_view_mode()

    def _build_view_mode(self):
        self.view_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.view_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(self.view_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            header, 
            text=self.period_title, 
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="right")
        
        ctk.CTkButton(
            header, 
            text="تعديل الدرجات / Edit Grades", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            width=140, height=32, corner_radius=6,
            fg_color=ACCENT_EMERALD, hover_color=ACCENT_EMERALD_HOVER,
            command=self.show_edit_mode
        ).pack(side="left")
        
        # Course List
        list_container = ctk.CTkFrame(self.view_frame, fg_color=BG_INNER, corner_radius=8)
        list_container.pack(fill="x", padx=20, pady=(0, 20))
        
        for enr in self.enrollments:
            row = ctk.CTkFrame(list_container, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=10)
            
            ctk.CTkLabel(
                row, 
                text=enr['name'], 
                font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                text_color=TEXT_MAIN
            ).pack(side="right")
            
            score_text = str(enr['score']) if enr['score'] is not None else "—"
            
            # Badge for score
            score_badge = ctk.CTkFrame(row, fg_color="transparent", border_width=1, border_color="#374151", corner_radius=6)
            score_badge.pack(side="left")
            ctk.CTkLabel(
                score_badge, 
                text=f"الدرجة: {score_text}", 
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=ACCENT_EMERALD
            ).pack(padx=10, pady=2)

    def _build_edit_mode(self):
        self.edit_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.edit_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(self.edit_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            header, 
            text=f"{self.period_title} (وضع التعديل)", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color="#F59E0B" # Warning/Orange color to indicate active edit mode
        ).pack(side="right")
        
        # Editable Course List
        self.entry_vars = {}
        list_container = ctk.CTkFrame(self.edit_frame, fg_color=BG_INNER, corner_radius=8)
        list_container.pack(fill="x", padx=20, pady=(0, 20))
        
        for enr in self.enrollments:
            row = ctk.CTkFrame(list_container, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=10)
            
            ctk.CTkLabel(
                row, 
                text=enr['name'], 
                font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                text_color=TEXT_MAIN
            ).pack(side="right")
            
            score_var = ctk.StringVar(value=str(enr['score']) if enr['score'] is not None else "")
            self.entry_vars[enr['id']] = score_var
            
            entry = ctk.CTkEntry(
                row, 
                textvariable=score_var, 
                width=80, height=32, 
                justify="center",
                fg_color="#0F111A", border_color="#374151"
            )
            entry.pack(side="left")

        # Action Buttons
        actions = ctk.CTkFrame(self.edit_frame, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkButton(
            actions, 
            text="حفظ / Save", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=120, height=34, corner_radius=6,
            fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER,
            command=self._handle_save
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            actions, 
            text="إلغاء / Cancel", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=120, height=34, corner_radius=6,
            fg_color="transparent", border_width=1, border_color="#4B5563",
            text_color=TEXT_MAIN, hover_color="#374151",
            command=self.show_view_mode
        ).pack(side="left")

    def show_view_mode(self):
        """Hides the edit form, shows the static view."""
        self.edit_frame.grid_forget()
        self.view_frame.grid(row=0, column=0, sticky="nsew")

    def show_edit_mode(self):
        """Hides the static view, shows the edit form."""
        self.view_frame.grid_forget()
        self.edit_frame.grid(row=0, column=0, sticky="nsew")

    def _handle_save(self):
        """Simulates saving the data and updating the UI."""
        for enr in self.enrollments:
            new_val = self.entry_vars[enr['id']].get().strip()
            enr['score'] = float(new_val) if new_val.replace('.', '', 1).isdigit() else None
            
        # Rebuild view mode to reflect new data
        self.view_frame.destroy()
        self._build_view_mode()
        self.show_view_mode()


# =============================================================================
# MAIN STUDENT PROFILE SCREEN
# =============================================================================
class StudentProfileScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_MAIN, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_identity_card()
        self._build_academic_section()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 15))
        header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            header, 
            text="الطلاب — Students", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
            text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="e")
        
        ctk.CTkButton(
            header, 
            text="عودة / Back", 
            width=100, height=32, corner_radius=6,
            fg_color="transparent", border_width=1, border_color="#4B5563",
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

    def _build_identity_card(self):
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color="#2A2D35")
        card.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 20))
        card.grid_columnconfigure(0, weight=1)
        
        # Top banner of the card
        banner = ctk.CTkFrame(card, fg_color=BG_INNER, corner_radius=12)
        banner.pack(fill="x", padx=2, pady=2)
        
        ctk.CTkLabel(
            banner, 
            text="اديان عبدالامير فخري احمد — Adian Abdulameer Fakhri Al-Asadi", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="right", padx=20, pady=15)
        
        # Action buttons in banner
        ctk.CTkButton(
            banner, text="حذف / Delete", width=100, height=30, fg_color="#EF4444", hover_color="#DC2626"
        ).pack(side="left", padx=(20, 5), pady=15)
        ctk.CTkButton(
            banner, text="تعديل / Edit", width=100, height=30, fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER
        ).pack(side="left", padx=5, pady=15)
        
        # Info Grid (RTL layout)
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=20)
        info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        fields = [
            ("نظام الدراسة / Study System", "نظام فصلي"),
            ("القسم / Department", "علوم الحاسوب"),
            ("تاريخ الميلاد / Date of Birth", "1997-01-01"),
            ("سنة القبول / Admission Year", "2015"),
            ("محل الولادة / Birthplace", "البصرة"),
            ("الجنسية / Nationality", "العراق"),
            ("المعدل / Average", "66.9 (متوسط)"),
            ("نوع الدراسة / Study Type", "مسائي / Evening"),
        ]
        
        for idx, (label, value) in enumerate(fields):
            row = idx // 2
            col = 2 if idx % 2 == 0 else 0
            
            # Label
            ctk.CTkLabel(info_frame, text=label, text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).grid(row=row, column=col+1, sticky="e", padx=(10, 20), pady=8)
            # Value box
            val_box = ctk.CTkFrame(info_frame, fg_color=BG_INNER, corner_radius=6)
            val_box.grid(row=row, column=col, sticky="ew", padx=10, pady=8)
            ctk.CTkLabel(val_box, text=value, text_color=TEXT_MAIN, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="e", padx=15, pady=6)

    def _build_academic_section(self):
        section_header = ctk.CTkFrame(self, fg_color="transparent")
        section_header.grid(row=2, column=0, sticky="ew", padx=30, pady=(10, 15))
        section_header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            section_header, 
            text="السجل الأكاديمي والدرجات — Academic Record & Grades", 
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=TEXT_MAIN
        ).grid(row=0, column=0, sticky="e")
        
        # Dummy Data for 2 periods
        period_1_courses = [
            {"id": 1, "name": "برمجة حاسوب 1 / Computer Programming I", "score": 75},
            {"id": 2, "name": "هياكل بيانات / Data Structures", "score": 82},
            {"id": 3, "name": "تصميم منطقي / Logic Design", "score": 68},
        ]
        
        period_2_courses = [
            {"id": 4, "name": "برمجة كائنية التوجه / OOP", "score": 90},
            {"id": 5, "name": "قواعد بيانات / Databases", "score": 78},
        ]
        
        # Instantiate the inline swappable cards
        card1 = InlineAcademicCard(self, "الفصل الأول / Term 1 — 2016-2017", period_1_courses)
        card1.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 15))
        
        card2 = InlineAcademicCard(self, "الفصل الثاني / Term 2 — 2016-2017", period_2_courses)
        card2.grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 30))

# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Modern Student Profile Preview")
        self.geometry("1100x850")
        
        # Force dark mode for the preview
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG_MAIN)
        
        self.main_screen = StudentProfileScreen(self)
        self.main_screen.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()