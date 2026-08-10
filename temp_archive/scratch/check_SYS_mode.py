import sys
import winreg


def is_windows_dark_mode() -> bool:
    """Returns True if Windows app mode is Dark, False if Light."""
    if sys.platform != "win32":
        return False

    try:
        registry_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0 = Dark Mode, 1 = Light Mode
    except Exception as err:
        print(f"Error reading Windows registry: {err}")
        return False


def get_windows_system_mode() -> str:
    """Returns 'Dark' or 'Light' based on Windows Personalization settings."""
    return "Dark" if is_windows_dark_mode() else "Light"


# --- Example Usage ---
if __name__ == "__main__":
    current_mode = get_windows_system_mode()
    print(f"Current Windows System Mode: {current_mode}")
