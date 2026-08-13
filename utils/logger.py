# =============================================================================
# utils/logger.py — System & Activity Logging Engine
# =============================================================================

import os
import sys
import logging
import traceback
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


def _write_to_file(filepath: str, log_line: str) -> None:
    """Helper to safely append a log line to a file inside logs/ folder."""
    try:
        dirname = os.path.dirname(filepath)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass


def log_system(msg: str, level: str = "INFO") -> None:
    """
    Log system-level actions (health checks, DB init, sync engine, network checks, errors & tracebacks)
    strictly to logs/system_log.txt, and output formatted colored status to terminal.
    """
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag, color = _format_level(level)
    log_line = f"{dt_str} {tag} {msg}"

    # Write strictly to logs/system_log.txt
    _write_to_file(os.path.join("logs", "system_log.txt"), log_line)

    try:
        print(f"{color}{log_line}{COLOR_RESET}", flush=True)
    except Exception:
        try:
            print(log_line.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


def log_activity(msg: str, level: str = "INFO") -> None:
    """
    Log user activity actions (login, logout, record additions/edits, deletions, certificate prints)
    strictly to logs/activity_log.txt, and output formatted colored status to terminal.
    """
    dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag, color = _format_level(level)
    log_line = f"{dt_str} {tag} {msg}"

    # Write strictly to logs/activity_log.txt
    _write_to_file(os.path.join("logs", "activity_log.txt"), log_line)

    try:
        print(f"{color}{log_line}{COLOR_RESET}", flush=True)
    except Exception:
        try:
            print(log_line.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


def setup_global_exception_logging() -> None:
    """
    Hook sys.excepthook and Python standard logging so that ALL uncaught exceptions,
    tracebacks, and system error messages get automatically saved to logs/system_log.txt.
    """
    # 1. Hook uncaught exceptions (tracebacks)
    def uncaught_exception_handler(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log_system(f"UNHANDLED EXCEPTION:\n{tb_text}", level="ERROR")

    sys.excepthook = uncaught_exception_handler

    # 2. Attach FileHandler to Python's root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    class SystemLogFileHandler(logging.Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                lvl = record.levelname
                log_system(msg, level=lvl)
            except Exception:
                pass

    # Avoid duplicate handlers
    has_custom = any(isinstance(h, SystemLogFileHandler) for h in root_logger.handlers)
    if not has_custom:
        root_logger.addHandler(SystemLogFileHandler())


# Automatically setup exception logging when logger module is imported
setup_global_exception_logging()
