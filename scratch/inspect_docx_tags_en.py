import docx
import os

doc_path = 'templets/year - Temp - En - D - SBS.docx'
if os.path.exists(doc_path):
    doc = docx.Document(doc_path)
    print("=== TABLES IN TEMPLATE ===")
    for t_idx, table in enumerate(doc.tables):
        print(f"Table {t_idx+1}:")
        for r_idx, row in enumerate(table.rows):
            cell_texts = [c.text.strip().replace('\n', ' ') for c in row.cells]
            print(f"  Row {r_idx+1}: {' | '.join(cell_texts)}")
