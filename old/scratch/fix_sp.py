with open('sql/SP.sql', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

sp_target = "PROCEDURE `sp_GetCertificate_StudentInfo`"
sp_pos = text.find(sp_target)
if sp_pos != -1:
    select_pos = text.find("s.graduation_date,", sp_pos)
    if select_pos != -1:
        insertion = "s.graduation_date,\n        s.graduation_semester,\n        s.date_of_birth,\n        s.sequence_number,\n        s.postgraduation_number,\n"
        old_part = "s.graduation_date,\n"
        text = text[:select_pos] + text[select_pos:].replace(old_part, insertion, 1)
        with open('sql/SP.sql', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Successfully updated sp_GetCertificate_StudentInfo in sql/SP.sql!")
    else:
        print("s.graduation_date not found in procedure!")
else:
    print("Procedure not found!")
