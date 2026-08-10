import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scratch.check_sp import show_proc_definition

if __name__ == "__main__":
    show_proc_definition("GetFullCertificateData")
