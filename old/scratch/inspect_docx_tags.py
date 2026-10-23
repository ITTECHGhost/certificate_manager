import zipfile
import re

docx_file = "templets/year - Temp - Ar - D - SBS.docx"

with zipfile.ZipFile(docx_file) as z:
    xml_content = z.read("word/document.xml").decode("utf-8")

text_only = re.sub(r'<[^>]+>', '', xml_content)
with open("scratch/extracted_docx_text.txt", "w", encoding="utf-8") as f:
    f.write(text_only)

print("Saved to scratch/extracted_docx_text.txt")
