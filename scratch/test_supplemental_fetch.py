import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from data.repositories import StudentRepository
from sync_engine import is_online, set_online

def verify_student_fields(student, description):
    print(f"  Verifying {description}: {student.get('full_name_ar', 'Unknown')}")
    
    # Check fields are present
    assert "sequence_number" in student, "sequence_number missing"
    assert "postgraduation_no" in student, "postgraduation_no missing"
    assert "postgraduation_number" in student, "postgraduation_number missing"
    
    seq = student.get("sequence_number")
    post_no = student.get("postgraduation_no")
    post_num = student.get("postgraduation_number")
    
    print(f"    sequence_number: {seq}")
    print(f"    postgraduation_no: {post_no}")
    print(f"    postgraduation_number: {post_num}")
    
    # Ensure they have identical values for postgrad columns
    assert post_no == post_num, f"Mismatch: {post_no} != {post_num}"

def run_tests():
    print("=== Testing Student Repository Supplemental Fetch ===")
    
    repo = StudentRepository()
    orig_online = is_online()
    
    # Run in both online/offline modes if online is True, or just current mode if offline
    modes = [orig_online]
    if orig_online:
        modes.append(False)
        
    for mode in modes:
        set_online(mode)
        mode_str = "ONLINE" if mode else "OFFLINE"
        print(f"\n--- Testing in {mode_str} Mode ---")
        
        # Test 1: get_all_paginated
        students = repo.get_all_paginated(limit=5)
        print(f"get_all_paginated returned {len(students)} records.")
        if students:
            verify_student_fields(students[0], "first student in paginated list")
            
            # Test 2: get_by_id
            sid = students[0]["id"]
            student_detail = repo.get_by_id(sid)
            assert student_detail is not None, f"Failed to fetch student ID {sid}"
            verify_student_fields(student_detail, f"student detail ID {sid}")
            
            # Test 3: search
            name_q = students[0]["full_name_ar"][:4] # Use first 4 chars for search query
            search_results = repo.search(name_q, limit=5)
            print(f"search query '{name_q}' returned {len(search_results)} records.")
            if search_results:
                # Find the record we searched for or verify the first result
                verify_student_fields(search_results[0], f"first search result for '{name_q}'")
        else:
            print("WARNING: No students available in database to perform verification.")

    # Restore original online status
    set_online(orig_online)
    print("\nALL SUPPLEMENTAL FETCH TESTS PASSED!")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\nTEST FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED EXCEPTION: {e}")
        sys.exit(1)
