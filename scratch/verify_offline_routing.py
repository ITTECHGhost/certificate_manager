import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import set_online
from data.repositories import (
    AcademicPeriodRepository,
    EnrollmentRepository,
    CourseRepository,
    PersonnelRepository,
    OfflineModeError,
)

def run_tests():
    print("=== STARTING OFFLINE ROUTING VERIFICATION TESTS ===")
    
    # 1. Set offline
    set_online(False)
    print(f"Network status set to is_online() = False")
    
    # 2. Test AcademicPeriodRepository.get_by_student
    print("\nTesting AcademicPeriodRepository.get_by_student(1) offline...")
    try:
        periods = AcademicPeriodRepository().get_by_student(1)
        print(f"  SUCCESS: returned {len(periods)} periods. Data: {periods[:2]}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 3. Test EnrollmentRepository.get_by_period
    print("\nTesting EnrollmentRepository.get_by_period(1) offline...")
    try:
        enrollments = EnrollmentRepository().get_by_period(1)
        print(f"  SUCCESS: returned {len(enrollments)} enrollments. Data: {enrollments[:2]}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 4. Test CourseRepository.get_all
    print("\nTesting CourseRepository.get_all() offline...")
    try:
        courses = CourseRepository().get_all()
        print(f"  SUCCESS: returned {len(courses)} courses. Data: {courses[:2]}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 5. Test CourseRepository.get_by_department
    print("\nTesting CourseRepository.get_by_department(1) offline...")
    try:
        courses_dept = CourseRepository().get_by_department(1)
        print(f"  SUCCESS: returned {len(courses_dept)} courses. Data: {courses_dept[:2]}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 6. Test Course write guards offline
    print("\nTesting CourseRepository write guards offline...")
    try:
        CourseRepository().insert({})
        print("  FAILED: CourseRepository.insert did not raise OfflineModeError")
        return False
    except OfflineModeError:
        print("  SUCCESS: CourseRepository.insert raised OfflineModeError as expected")
    except Exception as e:
        print(f"  FAILED with wrong exception: {e}")
        return False

    try:
        CourseRepository().update(1, {})
        print("  FAILED: CourseRepository.update did not raise OfflineModeError")
        return False
    except OfflineModeError:
        print("  SUCCESS: CourseRepository.update raised OfflineModeError as expected")
    except Exception as e:
        print(f"  FAILED with wrong exception: {e}")
        return False

    try:
        CourseRepository().delete(1)
        print("  FAILED: CourseRepository.delete did not raise OfflineModeError")
        return False
    except OfflineModeError:
        print("  SUCCESS: CourseRepository.delete raised OfflineModeError as expected")
    except Exception as e:
        print(f"  FAILED with wrong exception: {e}")
        return False

    # 7. Test Personnel write guards offline
    print("\nTesting PersonnelRepository write guards offline...")
    try:
        PersonnelRepository().insert({})
        print("  FAILED: PersonnelRepository.insert did not raise OfflineModeError")
        return False
    except OfflineModeError:
        print("  SUCCESS: PersonnelRepository.insert raised OfflineModeError as expected")
    except Exception as e:
        print(f"  FAILED with wrong exception: {e}")
        return False

    try:
        PersonnelRepository().update(1, {})
        print("  FAILED: PersonnelRepository.update did not raise OfflineModeError")
        return False
    except OfflineModeError:
        print("  SUCCESS: PersonnelRepository.update raised OfflineModeError as expected")
    except Exception as e:
        print(f"  FAILED with wrong exception: {e}")
        return False

    print("\n=== ALL OFFLINE ROUTING TESTS PASSED SUCCESSFULLY ===")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
