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
                
                # We want to find the <w:tr> that contains 'sequence_ON'
                # and strip '{%tr endif %}' from it, then append '{%tr endif %}' to '{%tr if sequence_ON %}'.
                
                # Split XML by <w:tr>
                rows = xml.split('<w:tr ')
                new_rows = [rows[0]]
                
                for row in rows[1:]:
                    if 'sequence_ON' in row:
                        # This is the row with sequence_ON
                        
                        # Remove all variations of {%tr endif %} in this row
                        # Because of Word formatting, it might be split across <w:t> tags
                        # Let's use a regex that matches {%tr followed by xml tags followed by endif %}
                        row = re.sub(r'\{%tr(?:<[^>]+>|\s)*endif(?:<[^>]+>|\s)*%\}', '', row)
                        
                        # Just in case there are stray pieces, we can also just strip literally
                        # Actually, docxtpl leaves it as it is until render time.
                        # Wait, what if the user wrote `{%tr endif %}` in a single run?
                        row = row.replace('{%tr endif %}', '')
                        row = row.replace('{%tr', '{%tr').replace('endif %}', '') # brute force?
                        
                        # Let's find the exact text of endif
                        # Let's just remove the word 'endif' from this row completely!
                        # The word 'endif' should not exist in this row except for the tag.
                        row = row.replace('endif', '')
                        
                        # Now find the place where sequence_ON is
                        # And insert {%tr endif %} immediately after the closing %} of sequence_ON
                        # Wait, if we just insert it right after the closing %} of the if tag...
                        # Actually, if we just append {%tr endif %} at the very end of the row string (before </w:tr>), docxtpl will see it.
                        row = row.replace('</w:tr>', '<w:r><w:t xml:space="preserve">{%tr endif %}</w:t></w:r></w:tr>')
                        
                    new_rows.append(row)
                
                xml = '<w:tr '.join(new_rows)
                zout.writestr(item, xml.encode('utf-8'))
            else:
                zout.writestr(item, content)

# Replace original file
import shutil
shutil.copy(out_path, docx_path)
print("Docx fixed and replaced!")
