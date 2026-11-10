"""Windows PowerShell 5.1 reads a .ps1 without a BOM in the ANSI code page: Arabic (or any
non-ASCII) text in it breaks the script's parsing. Keep every .ps1 plain ASCII."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_ps1_is_ascii():
    files = subprocess.run(["git", "ls-files", "*.ps1"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    files += [str(p.relative_to(ROOT)) for p in (ROOT / "installer" / "update").glob("*.ps1")]
    bad = []
    for rel in set(files):
        data = (ROOT / rel).read_bytes()
        if any(b > 127 for b in data):
            bad.append(rel)
    assert not bad, f"non-ASCII text in PowerShell files (PowerShell 5 breaks on it): {bad}"
