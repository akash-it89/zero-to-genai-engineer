"""Feature: rag-studio — deployment-artifact smoke tests (Req 13.1-13.5, 13.7).

Confirms `requirements.txt`, the frontend `package.json`, the backend `.env.example`,
the frontend env example, and the README all exist and are well-formed.
"""
from __future__ import annotations

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts: str) -> str:
    with open(os.path.join(PROJECT_ROOT, *parts), "r", encoding="utf-8") as fh:
        return fh.read()


def test_requirements_txt_exists_and_lists_core_dependencies():
    content = _read("requirements.txt")
    for package in ("fastapi", "uvicorn", "hypothesis", "pytest", "chromadb", "sentence-transformers"):
        assert package in content, f"requirements.txt is missing '{package}'"


def test_backend_env_example_exists_and_documents_required_keys():
    content = _read(".env.example")
    assert "OPENAI_API_KEY" in content
    assert "RAG_STUDIO_CORS_ORIGINS" in content
    # Placeholder values only — never a real-looking secret committed to the repo.
    assert "sk-your-openai-key-here" in content


def test_frontend_package_json_exists_and_is_well_formed():
    content = _read("frontend", "package.json")
    data = json.loads(content)
    assert data["name"] == "frontend"
    for script in ("dev", "build", "test:e2e"):
        assert script in data["scripts"], f"frontend/package.json is missing the '{script}' script"
    assert "@playwright/test" in data.get("devDependencies", {})


def test_frontend_env_example_exists_and_documents_api_base_url():
    content = _read("frontend", ".env.example")
    assert "VITE_API_BASE_URL" in content


def test_readme_exists_and_documents_start_commands():
    content = _read("README.md")
    assert "uvicorn backend.main:app" in content
    assert "npm install" in content
    assert "npm run dev" in content
    assert "npm run build" in content
    assert "VITE_API_BASE_URL" in content
    # Both servers are long-running and manually started, not auto-launched.
    assert "manually" in content.lower()
