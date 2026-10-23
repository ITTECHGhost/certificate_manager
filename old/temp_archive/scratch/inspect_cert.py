import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.repositories import CertificateRepository

def inspect_cert_detail(student_id):
    print(f"Student ID: {student_id}")
    cert_repo = CertificateRepository()
    rowsets = cert_repo._call_read_multi("GetFullCertificateData", (student_id,))
    print(f"  Number of rowsets returned: {len(rowsets)}")
    for idx, rset in enumerate(rowsets):
        print(f"    Rowset {idx}: length = {len(rset)}")
        if rset:
            print(f"      Keys of first row: {list(rset[0].keys())}")
    print("-" * 50)

if __name__ == "__main__":
    for sid in [2, 4, 6, 8]:
        inspect_cert_detail(sid)
