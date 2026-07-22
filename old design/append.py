
with open('data/queries.py', 'a', encoding='utf-8') as f:
    f.write('''

# =============================================================================
# FILE-BASED ACTIVITY LOGGING
# =============================================================================

import os

def _read_activity_logs() -> list[dict]:
    log_path = "activity_log.txt"
    if not os.path.exists(log_path):
        return []
        
    logs = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                parts = line.split(" [ACTIVITY] ", 1)
                if len(parts) == 2:
                    dt = parts[0].split(",")[0]
                    msg = parts[1].strip()
                    logs.append({
                        "id": len(logs),
                        "table_name": "System",
                        "action": "INFO",
                        "summary": msg,
                        "created_at": dt,
                        "error_info": None
                    })
    except Exception:
        pass
        
    return list(reversed(logs))

def count_audit_log(table_filter: str = "", action_filter: str = "") -> int:
    return len(_read_activity_logs())

def get_audit_log(table_filter: str = "", action_filter: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    return _read_activity_logs()[offset:offset+limit]

def clear_audit_logs() -> None:
    try:
        with open("activity_log.txt", "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass
''')
