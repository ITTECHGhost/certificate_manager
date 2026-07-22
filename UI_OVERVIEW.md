# Certificate Manager UI Architecture Overview

This document outlines the user interface system, design aesthetics, components, and layout architecture of the Certificate Manager application.

---

## 1. Visual Design & Theme Engine

The application has been upgraded to leverage **NiceGUI**, delivering a modern, premium, and responsive web-based UI wrapped as a native desktop application (via PyWebView).

### Core Aesthetic Principles
- **Modern Web Design**: Heavy usage of Quasar Framework and TailwindCSS utility classes for layout, typography, and spacing.
- **Glassmorphism & Shadows**: The UI implements deep layered shadows (e.g. `shadow-blue-600/35`) and high contrast container boundaries for a sleek, premium feel.
- **Theme Awareness**: The `nicegui_ui/ui_theme.py` system dynamically detects OS color schemes and explicitly provides dark/light mode CSS tokens (such as `card_background`, `text_main`, `border_color`).

---

## 2. Layout Structure & UI Components

The `nicegui_ui/` namespace manages UI logic and abstractions to keep screen files clean.

### The UI Component Factory (`ui_components.py`)
All core components are rendered through the `UI` factory class to guarantee consistency across the app.
- **`UI.card()`**: Reusable container enforcing border radii, background padding, and contrast colors.
- **`UI.primary_button()` / `UI.secondary_button()`**: Abstracted action buttons injected with the current global theme accent color and tailored hover transitions.
- **Section Headers**: Built-in bilingual headers (Arabic — English) ensuring typography standardization across modules.

### State & Routing Management
- **`state.py`**: Manages the global `app_session`, handling secure user login storage, active accent colors, and global cache tracking.
- **`N_main.py` (Router)**: Registers all active `@ui.page` routes.

---

## 3. Key Screen Views

The active interface logic resides entirely inside the `nicegui_screens/` namespace:

- **`login_screen.py` (`/`)**: A two-column split-screen layout displaying the institutional logo on the left and a glowing, theme-aware authentication card on the right. Form inputs are bound directly to NiceGUI event loops and validated against the backend `AuthRepository`.
- **`dashboard_screen.py` (`/dashboard`)**: The primary navigation hub accessible post-login. Implements an overarching layout wrapper (header navbar, sidebar drawer) and loads modular content based on user interaction. Features responsive stat-cards and quick actions.
- **(Planned/In-Progress) `students_screen.py` / `settings_screen.py`**: Remaining screens follow the same `UI` factory patterns, extending the dashboard framework for complex data visualization and CRUD operations.

*(Note: All legacy CustomTkinter architectures and screen definitions have been securely archived in the `old design/` directory and are no longer part of the execution lifecycle).*
