"""Feature: rag-studio — backend smoke tests (Req 9.6, 9.7, 9.8, 10.1, 10.3, 13.6, 14.6, 14.7).

`rag` imports/runs without FastAPI installed (tier separation); the backend starts,
enables CORS, and serves endpoints; `/health` warns on absent optional keys; an
auth error takes precedence over a data error.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from rag.pipeline import RagStudioPipeline


def _fresh_app():
    tmp = tempfile.mkdtemp()
    pipeline = RagStudioPipeline(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")
    return create_app(pipeline=pipeline)


def test_rag_package_imports_without_fastapi_installed():
    # Tier separation (Req 10.1, 12.1): the `rag` package must not require FastAPI.
    script = (
        "import builtins\n"
        "_orig_import = builtins.__import__\n"
        "def _blocking_import(name, *a, **k):\n"
        "    if name == 'fastapi' or name.startswith('fastapi.'):\n"
        "        raise ImportError('fastapi is not installed')\n"
        "    return _orig_import(name, *a, **k)\n"
        "builtins.__import__ = _blocking_import\n"
        "import rag.interfaces, rag.config, rag.registry, rag.governance, rag.pipeline\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=".", capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_backend_starts_and_serves_health():
    app = _fresh_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_warns_on_absent_optional_keys(monkeypatch):
    for key in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    app = _fresh_app()
    client = TestClient(app)
    resp = client.get("/health")
    warnings = " ".join(resp.json()["warnings"])
    assert "OPENAI_API_KEY" in warnings
    assert "OPENROUTER_API_KEY" in warnings


def test_cors_headers_present_for_configured_origin(monkeypatch):
    monkeypatch.setenv("RAG_STUDIO_CORS_ORIGINS", "http://localhost:5173")
    app = _fresh_app()
    client = TestClient(app)
    resp = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_auth_error_precedes_data_error():
    app = _fresh_app()
    client = TestClient(app)
    # No X-Principal-Id header AND an invalid empty-question body — auth must win.
    resp = client.post("/chat", json={"question": ""})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_valid_principal_but_bad_data_yields_400_not_401():
    app = _fresh_app()
    client = TestClient(app)
    resp = client.post("/chat", json={"question": ""}, headers={"X-Principal-Id": "alice"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_options_endpoint_requires_auth_and_serves_catalog():
    app = _fresh_app()
    client = TestClient(app)
    unauth = client.get("/options")
    assert unauth.status_code == 401

    authed = client.get("/options", headers={"X-Principal-Id": "alice"})
    assert authed.status_code == 200
    assert "embedding" in authed.json()
