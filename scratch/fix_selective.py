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
                
                # Replace EXACTLY the sequence_ON tags
                # Because word splits tags across w:t, we replace '{%tr' with '{%' only when 'sequence_ON' is right next to it.
                # Actually, docxtpl strips <w:t> dynamically, but we have to modify the raw XML string.
                
                # We know from earlier exactly what they look like:
                xml = xml.replace('{%tr</w:t></w:r><w:r w:rsidR="002F4C41"><w:t xml:space="preserve"> if </w:t></w:r><w:proofErr w:type="spellStart"/><w:r w:rsidR="002F4C41"><w:t>sequence_ON</w:t>',
                                  '{%</w:t></w:r><w:r w:rsidR="002F4C41"><w:t xml:space="preserve"> if </w:t></w:r><w:proofErr w:type="spellStart"/><w:r w:rsidR="002F4C41"><w:t>sequence_ON</w:t>')
                
                xml = xml.replace('<w:t xml:space="preserve">{%tr endif %}</w:t>', '<w:t xml:space="preserve">{% endif %}</w:t>')
                
                zout.writestr(item, xml.encode('utf-8'))
            else:
                zout.writestr(item, content)

shutil.copy(out_path, docx_path)
print("Replaced {%tr if sequence_ON %} with {% if sequence_ON %}")
