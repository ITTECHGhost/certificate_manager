import zipfile
import shutil
import os

docx_path = r'templets\semester - Temp - En - D.docx'
out_path = r'templets\semester - Temp - En - D_fixed.docx'

with zipfile.ZipFile(docx_path, 'r') as zin:
    with zipfile.ZipFile(out_path, 'w') as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = content.decode('utf-8')
                
                # Replace {% tr with {%tr
                xml = xml.replace('{% tr', '{%tr')
                
                # Also check for {%p and {%tc spaces just in case
                xml = xml.replace('{% p', '{%p')
                xml = xml.replace('{% tc', '{%tc')
                
                # And fix endif%} to endif %}
                xml = xml.replace('endif%}', 'endif %}')
                xml = xml.replace('Passed_ON%}', 'Passed_ON %}')
                
                zout.writestr(item, xml.encode('utf-8'))
            else:
                zout.writestr(item, content)

shutil.copy(out_path, docx_path)
print("Removed spaces from docxtpl tags!")
