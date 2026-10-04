# =============================================================================
# tools/build_apps.py — Deployment & Executable Build Automation
# =============================================================================
#
# PURPOSE:
#   Automates building standalone executable packages for PyInstaller:
#   1. Main Laptop (Server + Client App)
#   2. Secondary Laptop (Client App Only, network-connected to Server IP)
#
# =============================================================================

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"

def run_cmd(cmd: list[str]) -> None:
    print(f"\n[BUILD] Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"[BUILD ERROR] Command failed with code {res.returncode}")
        sys.exit(res.returncode)

def create_server_starter_scripts(output_dir: Path) -> None:
    """Creates batch scripts for running the Server API and Desktop Application."""
    start_server_bat = output_dir / "Start_Server_API.bat"
    with open(start_server_bat, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("echo Starting Certificate Manager Backend API Service on 0.0.0.0:2030...\n")
        f.write("start /B py -m uvicorn api.main:app --host 0.0.0.0 --port 2030\n")
        f.write("echo Backend API running on port 2030.\n")
        f.write("pause\n")

    start_app_bat = output_dir / "Start_Certificate_Manager.bat"
    with open(start_app_bat, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("echo Starting Certificate Manager Desktop Client...\n")
        f.write("start CertificateManager_App.exe\n")

def build_packages():
    print("=================================================================")
    print(" Certificate Manager — Packaging Automation Tool")
    print("=================================================================")
    
    # 1. Clean previous build artifacts
    if DIST_DIR.exists():
        print("[BUILD] Cleaning old dist/ directory...")
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    if BUILD_DIR.exists():
        print("[BUILD] Cleaning old build/ directory...")
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    # 2. Build Main App Executable using PyInstaller
    # PyInstaller flags:
    # --noconfirm: overwrite old spec/dist
    # --onedir: bundle into portable folder directory
    # --windowed: no console window popup
    # --collect-data nicegui
    # --collect-all nicegui
    pyinstaller_cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=CertificateManager_App",
        "--collect-all=nicegui",
        "--collect-all=webview",
        "--add-data=templets;templets",
        "--add-data=sql;sql",
        "--add-data=themes;themes",
        "--add-data=nicegui_ui;nicegui_ui",
        "--add-data=csit.png;.",
        "--add-data=server_config.json;.",
        "main.py"
    ]
    
    run_cmd(pyinstaller_cmd)

    app_dist_folder = DIST_DIR / "CertificateManager_App"
    if app_dist_folder.exists():
        print(f"\n[SUCCESS] Executable package created successfully at: {app_dist_folder}")

        # Create convenience launcher scripts
        create_server_starter_scripts(app_dist_folder)

        print("\n=================================================================")
        print(" DEPLOYMENT INSTRUCTIONS:")
        print("=================================================================")
        print(" 1. MAIN LAPTOP (SERVER + MAIN USER):")
        print("    - Copy the folder 'dist/CertificateManager_App' to the Main Laptop.")
        print("    - Double-click 'Start_Server_API.bat' to start the backend on port 2030.")
        print("    - Double-click 'Start_Certificate_Manager.bat' to launch the UI app.")
        print("    - Allow port 2030 in Windows Firewall for Inbound Connections.")
        print("\n 2. SECONDARY LAPTOP (SECONDARY USER):")
        print("    - Copy the folder 'dist/CertificateManager_App' to the Secondary Laptop.")
        print("    - Open 'server_config.json' and set 'host' to the Main Laptop's IP address")
        print("      (e.g., \"host\": \"192.168.1.50\").")
        print("    - Double-click 'Start_Certificate_Manager.bat' to launch the app.")
        print("    - The app will connect to the Main Laptop when online, and automatically")
        print("      switch to local offline mode when disconnected!")
        print("=================================================================\n")

if __name__ == "__main__":
    build_packages()
