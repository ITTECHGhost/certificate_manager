"""Shared helpers for the test suite (import as tests.helpers)."""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_DIR = PROJECT_ROOT / "certificate_manager_api"
SNAP_DIR = PROJECT_ROOT / "tests" / "snapshots"
GOLDEN_DIR = PROJECT_ROOT / "tests" / ".golden"


def run_probe(*args: str):
    """Run tests/api_probe.py in its own process inside the API folder; return its JSON result.

    The API and the client both have modules called api_config, config and db, so the
    API is never imported into the test process itself.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tests" / "api_probe.py"), *args],
        cwd=str(API_DIR), env=env, capture_output=True, text=True, encoding="utf-8", timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"api_probe failed with exit code {proc.returncode}:\n{proc.stderr[-4000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])
