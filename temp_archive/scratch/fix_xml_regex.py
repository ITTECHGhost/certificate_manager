import zipfile
import shutil
import re

docx_path = r'templets\semester - Temp - En - D.docx'
out_path = r'templets\semester - Temp - En - D_fixed.docx'

with zipfile.ZipFile(docx_path, 'r') as zin:
    with zipfile.ZipFile(out_path, 'w') as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = content.decode('utf-8')
                
                # 1. Fix {% tr -> {%tr, {% p -> {%p, {% tc -> {%tc
                # Matches {% followed by any tags/spaces, then a space, then tr/p/tc
                # and replaces the space with nothing.
                xml = re.sub(r'(\{%(?:<[^>]+>|\s)*)\s+(tr|tc|p)', r'\1\2', xml)
                
                # 2. Fix endif%} -> endif %}
                xml = re.sub(r'(endif|Passed_ON)\s*((?:<[^>]+>|\s)*)%\}', r'\1 \2%}', xml)
                
                zout.writestr(item, xml.encode('utf-8'))
            else:
                zout.writestr(item, content)

shutil.copy(out_path, docx_path)
print("Regex fix applied!")
