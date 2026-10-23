import customtkinter as ctk

# =============================================================================
# COLOR PALETTES
# =============================================================================
ACCENT_COLORS = {
    "blue": "#3B82F6",
    "purple": "#A855F7",
    "emerald": "#10B981"
}

# Theme backgrounds (Light, Dark)
BG_CONTENT = ("gray95", "#15171E")
BG_SIDEBAR = ("white", "#1B1E27")
BG_BOTTOM  = ("#1A1C23", "#0F1115")
BG_CARD    = ("white", "#222631")
TEXT_MAIN  = ("gray10", "gray95")
TEXT_MUTED = ("gray40", "gray60")

class ShadowCard(ctk.CTkFrame):
    def __init__(self, master, fg_color=("white", "#222631"), shadow_color=("#B0B8C1", "#08090C"), corner_radius=10, offset=5, **kwargs):
        # Master wrapper is completely transparent
        super().__init__(master, fg_color="transparent", **kwargs)
        
        # 1. The Shadow Layer (Pushed down and to the right via padding)
        self.shadow = ctk.CTkFrame(self, fg_color=shadow_color, corner_radius=corner_radius)
        self.shadow.pack(fill="both", expand=True, padx=(offset, 0), pady=(offset, 0))
        
        # 2. The Main Card Layer (Placed inside the shadow, but pulled up and to the left)
        self.card = ctk.CTkFrame(self.shadow, fg_color=fg_color, corner_radius=corner_radius)
        self.card.place(relx=0, rely=0, relwidth=1, relheight=1, x=-offset, y=-offset)

    def get_container(self):
        """Returns the front card so you can put widgets inside it."""
        return self.card


class DashboardDemo(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Certificate Management Dashboard")
        self.geometry("950x750")
        self.current_accent = "purple"
        
        # Set default appearance
        ctk.set_appearance_mode("light")
        self.configure(fg_color=BG_CONTENT)

        # Dynamic widgets lists to update when accent color changes
        self.accent_buttons = []
        self.accent_texts = []

        self._build_layout()
        self.set_accent_color(self.current_accent)

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Top Header ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(
            header_frame, 
            text="Certificate Management Dashboard", 
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        ).pack(side="left")

        # --- Main Content Area (Left) ---
        self.content_frame = ctk.CTkFrame(self, fg_color=BG_CONTENT, corner_radius=0)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self._build_main_content()

        # --- Sidebar Area (Right) ---
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0)
        self.sidebar_frame.grid(row=1, column=1, sticky="nsew")
        self._build_sidebar()

        # --- Bottom Panel (Theme & Stats) ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color=BG_BOTTOM, corner_radius=0)
        self.bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._build_bottom_panel()

    def _build_main_content(self):
        # 1. Dashboard Title
        title_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(title_frame, text="Dashboard", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Welcome back to the Certificate Management System", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED).pack(anchor="w")

        # 2. KPI Cards Grid
        kpi_grid = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        kpi_grid.pack(fill="x", pady=(0, 20))
        kpi_grid.grid_columnconfigure((0, 1), weight=1)

        kpi_data = [
            ("STUDENTS", "1618", "👤", 0, 0),
            ("DEPARTMENTS", "2", "🏢", 0, 1),
            ("COURSES", "185", "📚", 1, 0),
            ("PERSONNEL", "13", "👔", 1, 1),
        ]

        for title, val, icon, r, c in kpi_data:
            # Initialize our new ShadowCard with a strict height
            shadow_wrapper = ShadowCard(kpi_grid, height=90)
            shadow_wrapper.grid(row=r, column=c, padx=10, pady=10, sticky="ew")
            
            # CRITICAL FIX: This stops the card from stretching vertically
            shadow_wrapper.pack_propagate(False) 
            
            # Get the front surface of the card to place our text and icons
            card = shadow_wrapper.get_container()
            
            # Icon box
            icon_box = ctk.CTkFrame(card, fg_color=("gray90", "#2A2E39"), corner_radius=8, width=42, height=42)
            icon_box.place(x=15, y=20)
            icon_lbl = ctk.CTkLabel(icon_box, text=icon, font=ctk.CTkFont(size=20))
            icon_lbl.place(relx=0.5, rely=0.5, anchor="center")
            
            # Register the icon to change color when themes swap
            self.accent_texts.append(icon_lbl) 

            # Text Labels
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MUTED).place(x=75, y=15)
            ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=24, weight="bold"), text_color=TEXT_MAIN).place(x=75, y=35)

        # 3. Quick Actions
        ctk.CTkLabel(self.content_frame, text="Quick Actions", font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(10, 10))
        
        actions_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        actions_frame.pack(fill="x", pady=(0, 20))

        btn1 = ctk.CTkButton(actions_frame, text="Add New Student", font=ctk.CTkFont(weight="bold"), corner_radius=6)
        btn1.grid(row=0, column=0, padx=(0, 10), pady=(0, 10))
        
        btn2 = ctk.CTkButton(actions_frame, text="Issue Certificate", font=ctk.CTkFont(weight="bold"), corner_radius=6)
        btn2.grid(row=0, column=1, padx=(0, 10), pady=(0, 10))
        
        btn3 = ctk.CTkButton(actions_frame, text="Add New Course", font=ctk.CTkFont(weight="bold"), corner_radius=6)
        btn3.grid(row=1, column=0, padx=(0, 10))

        self.accent_buttons.extend([btn1, btn2, btn3])

        # 4. Recent Activity
        activity_card = ctk.CTkFrame(self.content_frame, fg_color=BG_CARD, corner_radius=10)
        activity_card.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        
        ctk.CTkLabel(activity_card, text="Recent Activity", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=20, pady=(15, 10))

        activities = [
            ("John Doe", "Issued", "2 mins ago"),
            ("Jane Smith", "Pending", "1 hour ago"),
            ("Global HR", "Updated", "3 hours ago"),
        ]

        for name, status, time in activities:
            row = ctk.CTkFrame(activity_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)
            
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=13), text_color=TEXT_MAIN, width=150, anchor="w").pack(side="left")
            
            status_lbl = ctk.CTkLabel(row, text=status, font=ctk.CTkFont(size=13, weight="bold"))
            status_lbl.pack(side="left", fill="x", expand=True)
            self.accent_texts.append(status_lbl)
            
            ctk.CTkLabel(row, text=time, font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="right")
            
            # Divider line
            ctk.CTkFrame(activity_card, height=1, fg_color=("gray90", "#2A2E39")).pack(fill="x", padx=20)

    def _build_sidebar(self):
        ctk.CTkLabel(
            self.sidebar_frame, 
            text="Management", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(anchor="w", padx=25, pady=(30, 20))

        nav_items = ["Home", "Students", "Departments", "Courses", "Personnel", "Change Log"]

        for item in nav_items:
            if item == "Home":
                # Active item
                self.nav_home = ctk.CTkFrame(self.sidebar_frame, corner_radius=6, height=35)
                self.nav_home.pack(fill="x", padx=20, pady=5)
                self.nav_home.pack_propagate(False)
                
                self.nav_home_text = ctk.CTkLabel(self.nav_home, text=item, font=ctk.CTkFont(size=13, weight="bold"))
                self.nav_home_text.place(x=15, rely=0.5, anchor="w")
                self.accent_texts.append(self.nav_home_text)
            else:
                # Inactive items
                lbl = ctk.CTkLabel(self.sidebar_frame, text=item, font=ctk.CTkFont(size=13), text_color=TEXT_MUTED)
                lbl.pack(anchor="w", padx=40, pady=12)

    def _build_bottom_panel(self):
        # 1. Stats Row
        stats_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=40, pady=(20, 10))
        
        stats_cols = [("Students", "1618"), ("Departments", "2"), ("Courses", "185"), ("Personnel", "13")]
        for i, (lbl, val) in enumerate(stats_cols):
            stats_frame.grid_columnconfigure(i, weight=1)
            col = ctk.CTkFrame(stats_frame, fg_color="transparent")
            col.grid(row=0, column=i)
            ctk.CTkLabel(col, text=lbl, font=ctk.CTkFont(size=12), text_color="gray80").pack()
            ctk.CTkLabel(col, text=val, font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack()

        # Divider
        ctk.CTkFrame(self.bottom_frame, height=1, fg_color="#2A2E39").pack(fill="x", padx=40, pady=10)

        # 2. Controls Row
        controls = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        controls.pack(fill="x", padx=40, pady=(5, 20))

        # Theme Segmented Button
        ctk.CTkLabel(controls, text="Theme", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(side="left", padx=(0, 20))
        
        self.theme_seg = ctk.CTkSegmentedButton(
            controls, 
            values=["light", "dark"],
            command=self.change_theme,
            selected_color="#1F2937",
            selected_hover_color="#374151",
            unselected_color="#111827",
            unselected_hover_color="#1F2937",
            text_color="white"
        )
        self.theme_seg.pack(side="left")
        self.theme_seg.set("light")

        # Accent Hue Segmented Button
        ctk.CTkLabel(controls, text="Accent Hue", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(side="left", padx=(40, 20))
        
        self.accent_seg = ctk.CTkSegmentedButton(
            controls, 
            values=["blue", "purple", "emerald"],
            command=self.set_accent_color,
            selected_color="#1F2937",
            selected_hover_color="#374151",
            unselected_color="#111827",
            unselected_hover_color="#1F2937",
            text_color="white"
        )
        self.accent_seg.pack(side="left")
        self.accent_seg.set("purple")

    def change_theme(self, mode_name):
        ctk.set_appearance_mode(mode_name)
        # Recalculate accent tinting for the sidebar active item based on mode
        self.set_accent_color(self.current_accent)

    def set_accent_color(self, color_name):
        self.current_accent = color_name
        hex_color = ACCENT_COLORS.get(color_name, "#A855F7")

        # Update solid buttons
        for btn in self.accent_buttons:
            btn.configure(fg_color=hex_color, hover_color=self._adjust_color_darker(hex_color))

        # Update text elements (Activity status, icons)
        for txt in self.accent_texts:
            txt.configure(text_color=hex_color)

        # Update active nav item background simulating transparency mix
        # If in light mode, use a very faint version of the color. If dark, slightly darker.
        if ctk.get_appearance_mode() == "Light":
            # Approximating a 10% opacity tint over white
            faint_bg = self._mix_colors("#FFFFFF", hex_color, 0.1)
        else:
            # Approximating a 15% opacity tint over dark gray
            faint_bg = self._mix_colors("#1B1E27", hex_color, 0.15)
            
        self.nav_home.configure(fg_color=faint_bg)

    def _adjust_color_darker(self, hex_color):
        """Simple utility to darken a hex color for hover states."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, r - 30)
        g = max(0, g - 30)
        b = max(0, b - 30)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _mix_colors(self, bg_hex, fg_hex, fg_alpha):
        """Simulates alpha blending of fg over bg."""
        bg_hex = bg_hex.lstrip('#')
        fg_hex = fg_hex.lstrip('#')
        bg = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        fg = tuple(int(fg_hex[i:i+2], 16) for i in (0, 2, 4))
        
        r = int(fg[0] * fg_alpha + bg[0] * (1 - fg_alpha))
        g = int(fg[1] * fg_alpha + bg[1] * (1 - fg_alpha))
        b = int(fg[2] * fg_alpha + bg[2] * (1 - fg_alpha))
        return f"#{r:02x}{g:02x}{b:02x}"

if __name__ == "__main__":
    app = DashboardDemo()
    app.mainloop()