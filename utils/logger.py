# =============================================================================
# utils/logger.py — System & Activity Logging Engine
# =============================================================================

import os
from datetime import datetime

# ANSI Color Codes for terminal formatting
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"


def _format_level(level: str) -> tuple[str, str]:
    """Return normalized level tag string and corresponding ANSI color code."""
    lvl = (level or "INFO").strip().upper()
    if lvl in {"ERROR", "FAILED"}:
        return "[ERROR]", COLOR_RED
    elif lvl in {"WARNING", "WARN"}:
        return "[WARNING]", COLOR_YELLOW
    elif lvl in {"OK", "SUCCESS"}:
        return "[OK]", COLOR_GREEN
    else:
        return "[INFO]", COLOR_CYAN


def log_system(msg: str, level: str = "INFO") -> None:
    """
    Log system-level actions (health checks, DB init, sync engine, network checks)
    directly to system_log.txt and output formatted colored status to terminal.
    """
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag, color = _format_level(level)
    log_line = f"{dt_str} {tag} {msg}"

    log_path = os.path.join("logs", "system_log.txt")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

    print(f"{color}{log_line}{COLOR_RESET}", flush=True)


def log_activity(msg: str, level: str = "INFO") -> None:
    """
    Log user activity actions (login, logout, record additions/edits, certificate prints)
    directly to activity_log.txt and output formatted colored status to terminal.
    """
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag, color = _format_level(level)
    log_line = f"{dt_str} {tag} {msg}"

    log_path = os.path.join("logs", "activity_log.txt")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

    print(f"{color}{log_line}{COLOR_RESET}", flush=True)
