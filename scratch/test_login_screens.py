import sys
import os
import customtkinter as ctk

# Add workspace root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import refresh_config
from main import Sidebar, HeaderBar

def test_screen_loading():
    print("Testing theme and UI widgets instantiation...")
    
    # We will test loading settings for user_id = 1
    # If MySQL is not running/accessible, refresh_config(1) will gracefully fall back
    # or fetch the appearance settings.
    try:
        refresh_config(1)
        print("refresh_config(1) ran successfully.")
    except Exception as e:
        print("refresh_config(1) failed, calling refresh_config(None) as fallback:", e)
        refresh_config(None)

    root = ctk.CTk()
    root.withdraw() # Hide window
    
    print("Creating Sidebar...")
    try:
        sidebar = Sidebar(root, on_navigate=lambda x: print(f"Navigating to {x}"))
        print("Sidebar created successfully!")
    except Exception as e:
        print("Sidebar creation failed!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    print("Creating HeaderBar...")
    try:
        header = HeaderBar(root)
        print("HeaderBar created successfully!")
    except Exception as e:
        print("HeaderBar creation failed!")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    root.destroy()
    print("All checks completed successfully!")

if __name__ == "__main__":
    test_screen_loading()
