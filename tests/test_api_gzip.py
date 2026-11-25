"""JSON answers are gzipped for slow links; file routes are not (2026-11-24, slow user laptop)."""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

import importlib.util  # noqa: E402

_API = Path(__file__).resolve().parents[1] / "certificate_manager_api"
sys.path.append(str(_API))
_spec = importlib.util.spec_from_file_location("api_main_for_gzip", _API / "main.py")
api_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api_main)

app = FastAPI()
app.add_middleware(api_main._JsonGZip)


@app.get("/students/search")
def _search():
    return [{"name": "طالب " * 50}] * 20


@app.get("/updates/download")
def _download():
    return Response(b"x" * 5000, media_type="application/octet-stream")


def test_json_is_gzipped():
    r = TestClient(app).get("/students/search", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and len(r.json()) == 20


def test_file_routes_are_not_gzipped():
    r = TestClient(app).get("/updates/download", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in r.headers and len(r.content) == 5000
