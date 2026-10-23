import re

with open('data/queries.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace import
content = content.replace('from db import get_connection, insert_audit_log', 
                          'import logging\nfrom db import get_connection\n\nactivity_logger = logging.getLogger("activity")\n\ndef log_activity(summary: str) -> None:\n    activity_logger.info(summary)')

# Replace insert_audit_log calls
content = re.sub(r'insert_audit_log\([^,]+,\s*[^,]+,\s*(.+?)\)', r'log_activity(\1)', content)

# Remove audit_log and personal_log functions
# We will just remove the whole "AUDIT LOG" section and related
# Let's just comment out or remove get_audit_log and count_audit_log
content = re.sub(r'# =+[\r\n]+# AUDIT LOG[\r\n]+# =+[\r\n]+(.*?)# =+[\r\n]+# COURSES', 
                 '# =============================================================================\n# COURSES', 
                 content, flags=re.DOTALL)

with open('data/queries.py', 'w', encoding='utf-8') as f:
    f.write(content)
