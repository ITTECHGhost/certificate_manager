from data.repositories import AcademicPeriodRepository

try:
    ap = AcademicPeriodRepository().get_by_student(1)
    print("Success:", ap)
except Exception as e:
    import traceback
    print("ERROR:")
    traceback.print_exc()
