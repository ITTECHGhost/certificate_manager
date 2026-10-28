import json

from tests.helpers import SNAP_DIR, run_probe

SNAPSHOT = SNAP_DIR / "api_routes.json"


def test_api_routes_unchanged_and_in_order(record_golden):
    current = run_probe("routes")
    if record_golden:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1), encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == expected
