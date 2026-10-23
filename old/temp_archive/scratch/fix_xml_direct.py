import re

with open('scratch/document.xml', 'r', encoding='utf-8') as f:
    xml = f.read()

# 1. Remove all {%tr endif %} from the document entirely!
xml = xml.replace('{%tr endif %}', '')

# 2. Find {%tr if sequence_ON %}
# Wait, it is split in XML: {%tr</w:t></w:r>... if ...sequence_ON... %}
# Let's just find "sequence_ON" and insert {%tr endif %} right after it.
# Actually, the problem is that it is missing {%tr endif %}. If we put it right after {%tr if sequence_ON %}, 
# docxtpl will see them both in the same table row, but since we removed {%tr endif %}, there won't be an extra endif.

# Let's find the position of "sequence_ON"
idx = xml.find('sequence_ON')
if idx != -1:
    # Find the closing %}
    idx_close = xml.find('%}', idx)
    if idx_close != -1:
        # Insert {%tr endif %} after it
        xml = xml[:idx_close+2] + '{%tr endif %}' + xml[idx_close+2:]

with open('scratch/document.xml', 'w', encoding='utf-8') as f:
    f.write(xml)

print("Modified document.xml")
