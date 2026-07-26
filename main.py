# =============================================================================
# main.py — Application Entry Point (NiceGUI Wrapper)
# =============================================================================
#
# HOW TO RUN:
#   python main.py
#
# WHAT THIS FILE DOES:
#   This file is a lightweight launcher that cleanly redirects to the active
#   NiceGUI primary entry point, N_main.py.
#
# =============================================================================

import sys
import runpy

if __name__ == "__main__":
    print("[main.py] Redirecting to NiceGUI entry point (N_main.py)...")
    runpy.run_path("N_main.py", run_name="__main__")

