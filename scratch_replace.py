import re

with open(r"c:\Users\alhayat\Music\certificate_manager\nicegui_screens\login_screen.py", "r", encoding="utf-8") as f:
    content = f.read()

new_build_ui = """    def build_ui(self) -> None:
        \"\"\"Renders the two-column split login layout using UI component factory.\"\"\"
        self.dark_mode = ui.dark_mode()
        
        # 1. Reset container padding & set background to adapt to theme
        ui.query(".nicegui-content").classes("p-0 m-0 bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        ui.query("body").classes("m-0 p-0 overflow-hidden bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        
        ui.add_head_html(
            \"\"\"
            <style>
                .login-card-glow {
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                    border: 1px solid rgba(226, 232, 240, 1);
                    position: relative;
                }
                .dark .login-card-glow {
                    box-shadow: 0 0 35px rgba(59, 130, 246, 0.15), 0 0 15px rgba(37, 99, 235, 0.1), 0 25px 50px rgba(0, 0, 0, 0.5);
                    border: 1px solid rgba(59, 130, 246, 0.2);
                }
                .dark .login-card-glow:hover {
                    box-shadow: 0 0 45px rgba(59, 130, 246, 0.25), 0 0 20px rgba(37, 99, 235, 0.15), 0 25px 50px rgba(0, 0, 0, 0.6);
                    border: 1px solid rgba(59, 130, 246, 0.35);
                }
                .custom-input .q-field__control {
                    background-color: #f8fafc !important;
                    border-radius: 10px !important;
                }
                .dark .custom-input .q-field__control {
                    background-color: #070e1e !important;
                }
                .custom-input .q-field__control:before {
                    border-color: rgba(148, 163, 184, 0.4) !important;
                }
                .dark .custom-input .q-field__control:before {
                    border-color: rgba(51, 65, 85, 0.7) !important;
                }
                .custom-input.q-field--focused .q-field__control:after {
                    border-color: #3b82f6 !important;
                    box-shadow: 0 0 8px rgba(59, 130, 246, 0.2) !important;
                }
                .dark .custom-input.q-field--focused .q-field__control:after {
                    box-shadow: 0 0 12px rgba(59, 130, 246, 0.35) !important;
                }
                
                /* Connecting network nodes pattern for dark mode background */
                .dark .bg-network {
                    background-image: radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.8) 0%, rgba(2, 6, 23, 1) 100%), url("data:image/svg+xml;utf8,<svg width='100' height='100' xmlns='http://www.w3.org/2000/svg'><circle cx='20' cy='20' r='1.5' fill='%23334155'/><circle cx='80' cy='40' r='1.5' fill='%23334155'/><circle cx='40' cy='80' r='1.5' fill='%23334155'/><path d='M20 20 L80 40 L40 80 Z' fill='none' stroke='%231e293b' stroke-width='0.5'/></svg>");
                    background-size: cover, 120px 120px;
                }
                .bg-network {
                    background-image: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                }
                
                /* Offset avatar */
                .avatar-offset {
                    position: absolute;
                    top: -32px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 10;
                }
            </style>
            <script>
            function syncThemeClasses() {
              const isDark = document.body && document.body.classList.contains('body--dark');
              if (isDark) {
                document.documentElement.classList.add('dark');
              } else {
                document.documentElement.classList.remove('dark');
              }
            }
            setInterval(syncThemeClasses, 100);
            </script>
            \"\"\"
        )

        # 2. Main 2-Column Split Container
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0 transition-colors duration-500"):
            
            # --- LEFT COLUMN: University Logo Area (50% or 60% width) ---
            with ui.column().classes(
                "w-1/2 md:w-3/5 h-full items-center justify-center p-8 bg-network transition-colors duration-500 border-r border-slate-200 dark:border-slate-800/50"
            ):
                if os.path.exists("csit.png"):
                    ui.image("csit.png").classes("w-[340px] max-w-full h-auto object-contain drop-shadow-xl dark:drop-shadow-[0_10px_30px_rgba(0,0,0,0.6)]")
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "text-4xl font-extrabold text-slate-500 dark:text-slate-400 tracking-wider text-center"
                    )

            # --- RIGHT COLUMN: Login Card Form Area (50% or 40% width) ---
            with ui.column().classes(
                "w-1/2 md:w-2/5 h-full items-center justify-center bg-slate-50 dark:bg-[#0f172a] p-6 transition-colors duration-500 relative"
            ):
                # The Card Container
                with ui.column().classes(
                    "w-[440px] max-w-full bg-white dark:bg-[#111827] rounded-[24px] p-8 pt-10 gap-5 transition-all duration-300 login-card-glow relative mt-8"
                ):
                    # Top User Badge Icon (Offset)
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-700/50 "
                        "flex items-center justify-center shadow-md dark:shadow-inner dark:shadow-blue-500/10 avatar-offset"
                    ):
                        with ui.element("div").classes("w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center"):
                            ui.icon("person_outline", size="sm").classes("text-slate-600 dark:text-slate-300")

                    # Title & Subtitle
                    with ui.column().classes("w-full items-center gap-1 text-center mt-2"):
                        ui.label("SYSTEM LOGIN / تسجيل الدخول").classes(
                            "text-[1.2rem] font-bold text-slate-800 dark:text-white tracking-wide"
                        )
                        ui.label("Enter credentials to access the system").classes(
                            "text-[11px] font-medium text-slate-500 dark:text-slate-400 -mb-0.5"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول").classes(
                            "text-[11px] font-medium text-slate-500 dark:text-slate-400"
                        )

                    # Username Input Group
                    with ui.column().classes("w-full gap-1 mt-3"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("Username").classes("text-xs text-slate-500 dark:text-slate-400 font-medium")
                            ui.label("اسم المستخدم").classes("text-xs font-bold text-slate-700 dark:text-slate-200")
                        
                        self.username_input = ui.input(
                            placeholder="Enter Username"
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense input-class="text-slate-800 dark:text-white font-semibold text-left"'
                        )
                        with self.username_input.add_slot('prepend'):
                            ui.icon('person_outline', size='sm').classes("text-slate-400 dark:text-slate-500 mr-1")
                        self.username_input.on('keydown.enter', self.handle_login)

                    # Password Input Group
                    with ui.column().classes("w-full gap-1"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("Password").classes("text-xs text-slate-500 dark:text-slate-400 font-medium")
                            ui.label("كلمة المرور").classes("text-xs font-bold text-slate-700 dark:text-slate-200")

                        self.password_input = ui.input(
                            placeholder="Enter Password",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense input-class="text-slate-800 dark:text-white font-semibold text-left"'
                        )
                        with self.password_input.add_slot('prepend'):
                            ui.icon('key', size='sm').classes("text-slate-400 dark:text-slate-500 mr-1")
                        self.password_input.on('keydown.enter', self.handle_login)

                    # Error Feedback Label
                    self.error_label = ui.label("").classes(
                        "text-red-500 dark:text-red-400 text-xs text-center w-full font-medium"
                    )
                    self.error_label.set_visibility(False)

                    # Primary Sign-In Button
                    with ui.button(on_click=self.handle_login).classes(
                        "w-full bg-[#3b82f6] hover:bg-[#2563eb] text-white font-bold "
                        "text-sm py-3 rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 normal-case transition-all mt-2 cursor-pointer flex-row justify-between px-6"
                    ):
                        ui.label("SIGN IN / تسجيل الدخول")
                        ui.icon("arrow_forward", size="sm")

                # Bottom Actions (Forgot Password & Theme Toggle)
                with ui.row().classes("w-[440px] max-w-full justify-between items-center mt-6 px-2"):
                    ui.link("Forgot Password? / هل نسيت كلمة المرور؟", "#").classes(
                        "text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 no-underline transition-colors"
                    )
                    with ui.row().classes("gap-2 items-center bg-white dark:bg-[#111827] px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-800 shadow-sm"):
                        ui.icon("dark_mode", size="xs").classes("text-slate-400 dark:text-slate-500")
                        ui.switch(on_change=lambda e: self.dark_mode.enable() if e.value else self.dark_mode.disable()).props("dense size=sm").bind_value(self.dark_mode, 'value')
                        ui.icon("light_mode", size="xs").classes("text-slate-500 dark:text-slate-400")
"""

pattern = re.compile(r"    def build_ui\(self\) -> None:.*?    def handle_login\(self, e=None\) -> None:", re.DOTALL)
new_content = pattern.sub(new_build_ui + "\n    def handle_login(self, e=None) -> None:", content)

with open(r"c:\Users\alhayat\Music\certificate_manager\nicegui_screens\login_screen.py", "w", encoding="utf-8") as f:
    f.write(new_content)
print("Done")
