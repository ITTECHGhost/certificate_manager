import json

import pytest

from tests.helpers import GOLDEN_DIR, PROJECT_ROOT, run_probe

GOLDEN = GOLDEN_DIR / "api_get.json"
PATHS_FILE = PROJECT_ROOT / "tests" / "golden_paths.txt"


def _paths() -> list:
    lines = PATHS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.mysql
def test_get_responses_match_golden(record_golden):
    current = run_probe("get", *_paths())
    if record_golden:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert current == expected
