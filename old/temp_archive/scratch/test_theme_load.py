import sys
import os
import customtkinter as ctk

# Add current directory to path
sys.path.append(os.getcwd())

from config import refresh_config
from db import init_db

def test_themes():
    print("Initializing DB...")
    init_db()
    
    # Test each theme
    themes = ["red", "orange", "purple"]
    for theme in themes:
        print(f"\nTesting theme: {theme}")
        try:
            # We need to simulate the DB setting for the theme
            from data.queries import get_db_connection
            with get_db_connection() as conn:
                conn.execute("UPDATE settings SET accent_color = ?", (theme,))
                conn.commit()
            
            # Now refresh config which loads the theme
            refresh_config()
            
            # Create a frame to see if it crashes during _draw (which happens on init)
            # CTk widgets need a root window to be fully initialized sometimes, 
            # but let's see if we can at least get past the refresh_config.
            print(f"Successfully loaded {theme} theme in config.")
            
            root = ctk.CTk()
            frame = ctk.CTkFrame(root)
            print(f"Successfully created CTkFrame with {theme} theme.")
            root.destroy()
            
        except Exception as e:
            print(f"FAILED theme {theme}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_themes()
