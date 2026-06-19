# Certificate Manager UI Architecture Overview

This document outlines the user interface system, design aesthetics, components, and layout architecture of the Certificate Manager application.

---

## 1. Visual Design & Theme Engine

The application leverages **CustomTkinter** to deliver a modern, premium, and responsive dark-themed and light-themed experience.

### Dynamic Theme Merging
- Built-in CustomTkinter themes (like `blue`) are used as a robust baseline layout configuration.
- Custom theme JSON files (`themes/orange.json`, `themes/purple.json`, `themes/red.json`) override specific colors while preserving necessary default widget styles (e.g. `corner_radius`, `border_width`).
- Theme settings are loaded globally during the startup lifecycle in `config.py` via `refresh_config()`.

### Instant Theme Switch (Programmatic Soft-Reboot)
- Inside the Settings screen, when a user saves a visual configuration change (accent colors or mode), the system writes it to the database and calls a soft-reboot:
  ```python
  import sys
  import os
  os.execl(sys.executable, sys.executable, *sys.argv)
  ```
- This triggers an instant reload of the entire app with the new theme applied immediately, bypassing manual restarts.

---

## 2. Layout Structure

The main application window (`main.py`) operates on a grid containing two main segments:
1. **Sidebar Navigation Frame (Right-Side, RTL Friendly):** Uses a fixed width of `230px` and lists primary navigation modules.
2. **Main Content slots (Left-Side):** Houses the `HeaderBar` (displaying network connectivity status and user profile indicators) and a Z-stack slots frame where active sub-screens are raised dynamically.

---

## 3. UI Component Registry

Reusable components reside in `ui/widgets.py` and enforce design consistency across screens:
- **Stat Cards (Dashboard):** Stat cards displaying icon, number count, and bilingual titles. Cards are aligned horizontally in a **1x4 grid** inside the dashboard:
  - Coordinate mapping: `row=0, col=0-3` with `weight=1` for columns to expand equally.
  - Custom text colors (`text_color=("gray10", "gray90")`) ensure perfect contrast and readability against their light (`gray98`) / dark (`gray16`) card backgrounds.
- **Section Headers:** Bilingual headers (`Arabic  —  English`) for secondary screen layouts.
- **Form Controls:** Labeled input boxes and option dropdown lists with built-in top-aligned text descriptions.

---

## 4. Key Screen Views

The interface consists of the following modular screens loaded under the `screens/` namespace:
- **`login_screen.py`**: A bilingual split-screen login page featuring the institutional logo and card input. To prevent startup/login race conditions, delayed focus is safely bound using `.winfo_exists()` checks.
- **`home_screen.py`**: The primary Dashboard dashboard containing stat counters (Students, Departments, Courses, Personnel) and quick actions.
- **`students_screen.py`**: A master-detail student record visualizer with built-in search bars, stage filtering, and an enrollment list.
- **`settings_screen.py`**: University metadata settings, appearance toggles, and database utility controllers (backup, restore, audit cleaner).
- **`certificate_screen.py`**: Document template builder and certificate generation module with document compilation tasks.
- **`history_screen.py`**: Log system parser tracking operations.
