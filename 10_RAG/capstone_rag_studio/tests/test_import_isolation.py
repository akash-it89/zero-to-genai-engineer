"""Feature: rag-studio — module import-isolation boundary (Req 12.6).

Static AST scan asserting no stage module imports another stage module's internals.
Cross-module reach is allowed ONLY through ``interfaces``, ``registry``, and ``config``.
This keeps the plug-and-play contract true at the source level and is re-run as the
package grows.
"""
from __future__ import annotations

import ast
import os

RAG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rag")

# Modules that are the shared contract — every stage module may import these.
ALLOWED_INTERNAL = {"interfaces", "registry", "config", "__init__"}

# Stage modules that must not import each other's internals. (Only those that exist
# are checked; the set grows as later waves land.)
STAGE_MODULES = {
    "stores", "retrieval", "query_transform", "post_retrieval", "rerank",
    "generate", "governance", "cache", "guardrails", "orchestrator",
    "observability", "evaluation", "persistence", "ingest",
}


def _rag_imports(path: str) -> set[str]:
    """Return the set of sibling `rag.*` submodules imported by a file."""
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "rag" and len(parts) >= 2:
                imported.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "rag" and len(parts) >= 2:
                    imported.add(parts[1])
    return imported


def test_no_cross_stage_internal_imports():
    if not os.path.isdir(RAG_DIR):
        return
    violations: list[str] = []
    for fname in os.listdir(RAG_DIR):
        if not fname.endswith(".py"):
            continue
        module = fname[:-3]
        if module not in STAGE_MODULES:
            continue
        for imported in _rag_imports(os.path.join(RAG_DIR, fname)):
            if imported == module:
                continue
            if imported not in ALLOWED_INTERNAL:
                violations.append(f"{module}.py imports rag.{imported} (only {sorted(ALLOWED_INTERNAL)} allowed)")
    assert not violations, "Cross-module import-isolation violations:\n" + "\n".join(violations)
