import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db import get_grade
from data.repositories import AuditRepository

def test_grade_casting():
    print("=== Testing get_grade casting ===")
    
    # Test valid floats/ints as strings and floats/ints
    assert get_grade(95) == ("امتياز", "Excellent")
    assert get_grade("92.5") == ("امتياز", "Excellent")
    assert get_grade(85.0) == ("جيد جداً", "Very Good")
    assert get_grade("81") == ("جيد جداً", "Very Good")
    assert get_grade(75) == ("جيد", "Good")
    assert get_grade("70.0") == ("جيد", "Good")
    assert get_grade(65) == ("متوسط", "Medium")
    assert get_grade("60") == ("متوسط", "Medium")
    assert get_grade(50) == ("مقبول", "Accepted")
    assert get_grade("45.5") == ("مقبول", "Accepted")
    
    # Test invalid string gracefully handled
    assert get_grade("not_a_float") == ("—", "—")
    assert get_grade(None) == ("—", "—")
    
    print("PASS: get_grade type casting works correctly.")

def test_audit_repository():
    print("\n=== Testing AuditRepository file-based logs ===")
    
    # Verify counts and retrieving logs
    repo = AuditRepository()
    count = repo.count_audit_log()
    print(f"Total audit logs in activity_log.txt: {count}")
    
    logs = repo.get_audit_log(limit=5)
    print(f"Retrieved first {len(logs)} logs:")
    for idx, log in enumerate(logs):
        print(f"  Log #{idx}: Time: {log['created_at']}, Msg: {log['summary']}")
        assert "created_at" in log
        assert "summary" in log
        assert log["table_name"] == "System"
        assert log["action"] == "INFO"

    print("PASS: AuditRepository file-based operations successful.")

if __name__ == "__main__":
    test_grade_casting()
    test_audit_repository()
