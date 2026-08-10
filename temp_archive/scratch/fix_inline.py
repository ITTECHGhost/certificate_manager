import zipfile
import shutil
import os

docx_path = r'templets\semester - Temp - En - D.docx'
out_path = r'templets\semester - Temp - En - D_fixed.docx'
original_backup = r'templets\semester - Temp - En - D_backup.docx'

# Use the original untouched backup from before my modifications if possible.
# Actually, I'll just use the current one and string replace.
with zipfile.ZipFile(docx_path, 'r') as zin:
    with zipfile.ZipFile(out_path, 'w') as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = content.decode('utf-8')
                
                # Replace {%tr if sequence_ON %} -> {% if sequence_ON %}
                xml = xml.replace('{%tr', '{%')
                # Wait, this would replace {%tr for row in period.rows %} as well!
                # We NEED {%tr for %} for the table rows to repeat!
                # So let's restore {%tr for %}
                xml = xml.replace('{% for row', '{%tr for row')
                xml = xml.replace('{% endfor %}', '{%tr endfor %}')
                
                # There are TWO {% endfor %} in the xml? Let's check.
                # Actually, docxtpl expects {%tr for row %} and {%tr endfor %} to match.
                
                zout.writestr(item, xml.encode('utf-8'))
            else:
                zout.writestr(item, content)

shutil.copy(out_path, docx_path)
print("Replaced {%tr if %} with {% if %}")
