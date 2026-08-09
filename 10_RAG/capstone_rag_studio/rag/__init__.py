"""RAG Studio — transport-agnostic RAG pipeline package.

This package contains ALL pipeline logic (ingestion, retrieval, governance,
reranking, generation, evaluation) and knows nothing about HTTP. Every pipeline
stage sits behind an abstract ``Stage_Interface`` in :mod:`rag.interfaces` and is
discovered through :mod:`rag.registry`. Modules reach each other ONLY through
``interfaces`` / ``registry`` / ``config`` — never by importing another stage
module's internals (enforced by ``tests/test_import_isolation.py``).
"""

__all__ = ["config", "interfaces", "registry"]

__version__ = "0.1.0"
