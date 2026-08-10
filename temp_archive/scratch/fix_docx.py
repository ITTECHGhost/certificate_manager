import zipfile
import re
import os

docx_path = r'templets\semester - Temp - En - D.docx'
out_path = r'templets\semester - Temp - En - D_fixed.docx'

with zipfile.ZipFile(docx_path, 'r') as zin:
    with zipfile.ZipFile(out_path, 'w') as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = content.decode('utf-8')
                
                # Find the tr that contains sequence_ON
                # We know docxtpl choked on it. Let's just remove {%tr if sequence_ON %} and {%tr endif %}
                # and manually wrap the row with standard {% if sequence_ON %} and {% endif %} outside the <w:tr>
                
                # 1. Remove the Jinja tags from the text
                xml = re.sub(r'\{%tr\s*if\s*sequence_ON\s*%\}', '', xml)
                # Note: Word might have split the tag. We need a more robust regex or just strip the XML tags temporarily to find it.
                # Actually, docxtpl's patch_xml does it. We can just use string replace for the exact matched parts we saw.
                
                # Let's write a function to strip the {%tr if sequence_ON %} and {%tr endif %} regardless of w:t splits
                pass
