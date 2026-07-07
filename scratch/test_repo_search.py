import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Reconfigure console output encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from sync_engine import set_online
from data.repositories import StudentRepository

def test_repo_search():
    # Set to online to test live API search
    set_online(True)
    
    print("Calling StudentRepository().search('ad')...")
    results = StudentRepository().search("ad")
    print(f"Got {len(results)} results:")
    for r in results:
        print(r)

if __name__ == "__main__":
    test_repo_search()
