with open('sql/SP.sql', 'r', encoding='utf-8', errors='ignore') as f:
    sql_text = f.read()

# Let's replace SELECT COALESCE(c.name_ar, '') AS subject_name with EN and AR versions
old_select = "COALESCE(c.name_ar, '') AS subject_name,"
new_select = """COALESCE(c.name_ar, '') AS subject_name,
   COALESCE(c.name_en, c.name_ar, '') AS subject_name_en,
   COALESCE(c.name_ar, '') AS subject_name_ar,
   COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,"""

updated_sql = sql_text.replace(old_select, new_select)

with open('sql/SP.sql', 'w', encoding='utf-8') as f:
    f.write(updated_sql)

print("Updated sql/SP.sql with English course name columns.")
