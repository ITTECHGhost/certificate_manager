with open('sql/SP.sql', encoding='utf-8') as f:
    lines = f.readlines()

def print_proc(name):
    print(f"=== {name} ===")
    found = False
    count = 0
    for line in lines:
        if f"PROCEDURE `{name}`" in line:
            found = True
        if found:
            print(line, end="")
            count += 1
            if "END //" in line or count > 50:
                break
    print("\n")

print_proc("GetStudentsPaginated")
print_proc("GetStudentDossierByID")
