from docxtpl import DocxTemplate
import traceback

doc = DocxTemplate(r'templets\semester - Temp - En - D.docx')
try:
    doc.render({'sequence_ON': True})
except Exception as e:
    import sys
    tb = sys.exc_info()[2]
    # walk traceback
    while tb:
        if 'src_xml' in tb.tb_frame.f_locals:
            xml = tb.tb_frame.f_locals['src_xml']
            with open('scratch/xml.txt', 'w', encoding='utf-8') as f:
                f.write(xml)
            print("Wrote xml to scratch/xml.txt")
            break
        tb = tb.tb_next
