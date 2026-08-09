"""Registry of selectable strategies/models — the single source of truth.

Every option the UI can show in a selector is declared here, keyed by *stage
category*. The Backend_API builds the ``Options_Catalog`` solely from this registry
(Req 1.1, 1.6, 12.3), so the UI, API, and pipeline stay in sync.

Design rules:
* An option declares its ``key``, ``label``, the ``stage_interface`` it implements,
  an optional ``needs`` env key, a ``reserved`` flag (+ ``reserved_target``), and a
  lazy ``factory``.
* ``available`` is computed at read time from ``needs`` presence (Req 1.3, 9.3).
* This module imports NO provider SDKs at import time — factories import lazily — so
  ``rag`` is importable without FastAPI or heavy deps (tier separation, Req 10.1).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Option:
    """One selectable strategy/model in a stage category."""

    key: str
    label: str
    stage_interface: str                       # name of the ABC in rag.interfaces
    needs: Optional[str] = None                # required Env_Key, or None
    reserved: bool = False                     # Reserved_Extension_Slot (not in v1)
    reserved_target: Optional[str] = None      # target stage category for a reserved slot
    is_local: bool = False                     # runs without paid API calls (Req 22.3)
    factory: Optional[Callable] = None         # lazy constructor
    meta: dict = field(default_factory=dict)

    def available(self) -> bool:
        """Available iff not reserved and any required Env_Key is present (Req 1.3)."""
        if self.reserved:
            return False
        return self.needs is None or bool(os.getenv(self.needs))

    def snapshot(self) -> dict:
        """Serializable view for the Options_Catalog — never leaks factories or keys."""
        return {
            "key": self.key,
            "label": self.label,
            "stage_interface": self.stage_interface,
            "available": self.available(),
            "reserved": self.reserved,
            "reserved_target": self.reserved_target,
            "requires_key": self.needs,        # NAME only, never the value (Req 24.3)
            "is_local": self.is_local,
        }


# ---------------------------------------------------------------------------
# The registry: category -> {option_key: Option}
# ---------------------------------------------------------------------------

REGISTRY: dict[str, dict[str, Option]] = {}


def register_option(category: str, option: Option) -> None:
    """Add an option to a category (creates the category if new).

    This is the ONLY mutation point; adding a new strategy is a single call here plus
    the new module — no changes to existing modules, routes, or the UI (Req 12.4).
    """
    REGISTRY.setdefault(category, {})[option.key] = option


def _o(category: str, *args, **kwargs) -> None:
    register_option(category, Option(*args, **kwargs))


# --- parser (chosen at ingest by file type) ---
_o("parser", "pdf", "Layout-aware PDF (pymupdf4llm)", "Parser", is_local=True)
_o("parser", "html", "HTML (BSHTMLLoader)", "Parser", is_local=True)
_o("parser", "docx", "DOCX (Docx2txt)", "Parser", is_local=True)
_o("parser", "txt", "Plain text", "Parser", is_local=True)
_o("parser", "ocr", "Scanned image OCR (rapidocr)", "Parser", is_local=True)

# --- chunker ---
_o("chunker", "recursive", "Recursive character (default)", "Chunker", is_local=True)
_o("chunker", "token", "Fixed-size token", "Chunker", is_local=True)
_o("chunker", "semantic", "Semantic (embedding boundaries)", "Chunker")
_o("chunker", "markdown", "Markdown-header aware", "Chunker", is_local=True)

# --- embedding ---
_o("embedding", "openai-3-small", "OpenAI text-embedding-3-small (1536d)", "Embedder",
   meta={"dim": 1536, "model": "text-embedding-3-small"})
_o("embedding", "openai-3-large", "OpenAI text-embedding-3-large (3072d)", "Embedder",
   meta={"dim": 3072, "model": "text-embedding-3-large"})
_o("embedding", "bge-small", "BGE-small-en-v1.5 (local, 384d)", "Embedder", is_local=True,
   meta={"dim": 384, "model": "BAAI/bge-small-en-v1.5"})
_o("embedding", "minilm", "all-MiniLM-L6-v2 (local, 384d)", "Embedder", is_local=True,
   meta={"dim": 384, "model": "sentence-transformers/all-MiniLM-L6-v2"})

# --- vector_store ---
_o("vector_store", "memory", "In-memory (NumPy cosine)", "VectorStore", is_local=True)
_o("vector_store", "chroma", "Chroma (persistent, local)", "VectorStore", is_local=True)
_o("vector_store", "faiss", "FAISS (in-process ANN)", "VectorStore", is_local=True)
_o("vector_store", "pinecone", "Pinecone (managed)", "VectorStore", needs="PINECONE_API_KEY")

# --- query_transform ---
_o("query_transform", "none", "None (raw question)", "QueryTransformer", is_local=True)
_o("query_transform", "hyde", "HyDE (hypothetical document)", "QueryTransformer")
_o("query_transform", "multi_query", "Multi-Query expansion", "QueryTransformer")
_o("query_transform", "query_decomposition", "Query Decomposition", "QueryTransformer",
   reserved=True, reserved_target="query_transform")
_o("query_transform", "self_query", "Self-Querying (metadata filters)", "QueryTransformer",
   reserved=True, reserved_target="query_transform")

# --- retrieval ---
_o("retrieval", "dense", "Dense (semantic)", "Retriever")
_o("retrieval", "bm25", "Sparse BM25 (keyword)", "Retriever", is_local=True)
_o("retrieval", "hybrid_rrf", "Hybrid — Reciprocal Rank Fusion", "Retriever")
_o("retrieval", "hybrid_weighted", "Hybrid — weighted score fusion", "Retriever")

# --- post_retrieval ---
_o("post_retrieval", "none", "None", "PostRetrievalProcessor", is_local=True)
_o("post_retrieval", "contextual_compression", "Contextual Compression", "PostRetrievalProcessor")

# --- reranker ---
_o("reranker", "none", "None (first-stage order)", "Reranker", is_local=True)
_o("reranker", "cross_encoder", "Cross-encoder (ms-marco-MiniLM, local)", "Reranker", is_local=True)
_o("reranker", "flashrank", "FlashRank (CPU, local)", "Reranker", is_local=True)
_o("reranker", "cohere", "Cohere Rerank (API)", "Reranker", needs="COHERE_API_KEY")
_o("reranker", "llm_listwise", "LLM listwise rerank", "Reranker")

# --- generation_llm ---
_o("generation_llm", "gpt-4o-mini", "OpenAI gpt-4o-mini", "GenerationLLM",
   meta={"provider": "openai", "model": "gpt-4o-mini"})
_o("generation_llm", "gpt-4o", "OpenAI gpt-4o", "GenerationLLM",
   meta={"provider": "openai", "model": "gpt-4o"})
_o("generation_llm", "openrouter:anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (OpenRouter)",
   "GenerationLLM", needs="OPENROUTER_API_KEY",
   meta={"provider": "openrouter", "model": "anthropic/claude-3.5-sonnet"})
_o("generation_llm", "openrouter:google/gemini-2.0-flash-001", "Gemini 2.0 Flash (OpenRouter)",
   "GenerationLLM", needs="OPENROUTER_API_KEY",
   meta={"provider": "openrouter", "model": "google/gemini-2.0-flash-001"})
_o("generation_llm", "openrouter:meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B (OpenRouter)",
   "GenerationLLM", needs="OPENROUTER_API_KEY",
   meta={"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct"})

# --- orchestrator ---
_o("orchestrator", "linear", "Linear flow", "Orchestrator", is_local=True)
_o("orchestrator", "crag", "Corrective RAG (CRAG)", "Orchestrator",
   reserved=True, reserved_target="orchestrator")
_o("orchestrator", "self_rag", "Self-RAG", "Orchestrator",
   reserved=True, reserved_target="orchestrator")
_o("orchestrator", "agentic_rag", "Agentic RAG", "Orchestrator",
   reserved=True, reserved_target="orchestrator")

# --- cache ---
_o("cache", "off", "Disabled", "Cache", is_local=True)
_o("cache", "exact_match", "Exact-match cache (default)", "Cache", is_local=True)
_o("cache", "semantic", "Semantic cache", "Cache")

# --- guardrail ---
_o("guardrail", "off", "Disabled", "Guardrail", is_local=True)
_o("guardrail", "light", "Light input/output screening (default)", "Guardrail", is_local=True)

# --- evaluation ---
_o("evaluation", "ragas", "RAGAS", "EvaluationFramework")
_o("evaluation", "deepeval", "DeepEval (gpt-4o judge)", "EvaluationFramework")

# --- access_policy ---
_o("access_policy", "in_memory_sqlite", "In-memory/SQLite policy provider", "AccessPolicyProvider",
   is_local=True)

# --- reserved capability slots (not config fields; documented future extensions) ---
_o("graph_store", "graph_store", "Graph store (GraphRAG)", "VectorStore",
   reserved=True, reserved_target="graph_store")
_o("graph_retriever", "graph_retriever", "Graph retriever (GraphRAG)", "Retriever",
   reserved=True, reserved_target="graph_retriever")
_o("tool_integration", "tool_integration", "Tool integration (Agentic RAG)", "Orchestrator",
   reserved=True, reserved_target="tool_integration")
_o("vision_parser", "vision_parser", "Vision parser (Multimodal RAG)", "Parser",
   reserved=True, reserved_target="vision_parser")
_o("multimodal_embedder", "multimodal_embedder", "Multimodal embedder (Multimodal RAG)", "Embedder",
   reserved=True, reserved_target="multimodal_embedder")


# ---------------------------------------------------------------------------
# Config field <-> category mapping (for validation)
# ---------------------------------------------------------------------------

FIELD_TO_CATEGORY: dict[str, str] = {
    "chunk_strategy": "chunker",
    "embedding": "embedding",
    "vector_store": "vector_store",
    "query_transform": "query_transform",
    "retrieval": "retrieval",
    "post_retrieval": "post_retrieval",
    "reranker": "reranker",
    "llm": "generation_llm",
    "orchestrator": "orchestrator",
    "caching": "cache",
    "guardrails": "guardrail",
}


# ---------------------------------------------------------------------------
# Catalog + lookup + validation
# ---------------------------------------------------------------------------

def get_option(category: str, key: str) -> Optional[Option]:
    return REGISTRY.get(category, {}).get(key)


def options_snapshot() -> dict:
    """The Options_Catalog: every option annotated with availability + reserved flags.

    This is the single machine-readable list the Backend_API returns and the UI renders
    from (Req 1.2, 1.6, 12.7). Deterministically ordered for stable comparison.
    """
    return {
        category: {key: opt.snapshot() for key, opt in options.items()}
        for category, options in REGISTRY.items()
    }


def validate_config(config, *, check_availability: bool = True) -> list[str]:
    """Validate a PipelineConfig against the Registry (Req 2.6, 1.5, 4.8, 9.4, 16.6).

    Returns a list of human-readable error strings (empty == valid). Detects:
    * a field value not registered for its category (Req 2.6, 9 P9);
    * a selection whose required Env_Key is absent — names the key (Req 1.5, 4.8, 9.4);
    * a reserved extension slot selection — states it is unavailable in v1 (Req 16.6).
    """
    d = config.to_dict() if hasattr(config, "to_dict") else dict(config)
    errors: list[str] = []
    for field_name, category in FIELD_TO_CATEGORY.items():
        value = d.get(field_name)
        if value is None:
            continue
        opt = get_option(category, str(value))
        if opt is None:
            errors.append(f"Field '{field_name}': '{value}' is not a registered {category} option.")
            continue
        if opt.reserved:
            errors.append(
                f"Field '{field_name}': '{value}' is a reserved extension slot "
                f"unavailable in v1 (target category: {opt.reserved_target})."
            )
            continue
        if check_availability and not opt.available():
            errors.append(
                f"Field '{field_name}': '{value}' requires the environment key "
                f"'{opt.needs}', which is not set."
            )
    return errors


# ---------------------------------------------------------------------------
# Embedder / LLM factories (lazy provider imports)
# ---------------------------------------------------------------------------

import functools


@functools.lru_cache(maxsize=8)
def build_embedder(name: str):
    """Construct an Embedder implementation (lazy import of stores module)."""
    from rag import stores  # noqa: WPS433 (lazy by design)
    return stores.make_embedder(name)


@functools.lru_cache(maxsize=8)
def build_llm(name: str, temperature: float = 0.0):
    """Construct a GenerationLLM implementation (lazy import of generate module)."""
    from rag import generate  # noqa: WPS433
    return generate.make_llm(name, temperature)


@functools.lru_cache(maxsize=8)
def build_vector_store(name: str, *, dim: int = 384, persist_dir: str = ".chroma", index_name: str = "rag-studio"):
    """Construct a VectorStore implementation (lazy import of stores module)."""
    from rag import stores  # noqa: WPS433
    return stores.make_vector_store(name, dim=dim, persist_dir=persist_dir, index_name=index_name)


@functools.lru_cache(maxsize=8)
def build_retriever(mode: str):
    """Construct a Retriever implementation (lazy import of retrieval module)."""
    from rag import retrieval  # noqa: WPS433
    return retrieval.make_retriever(mode)


@functools.lru_cache(maxsize=8)
def build_query_transformer(name: str):
    """Construct a QueryTransformer implementation (lazy import of query_transform module)."""
    from rag import query_transform  # noqa: WPS433
    return query_transform.make_query_transformer(name)


@functools.lru_cache(maxsize=8)
def build_post_retrieval_processor(name: str):
    """Construct a PostRetrievalProcessor implementation (lazy import of post_retrieval module)."""
    from rag import post_retrieval  # noqa: WPS433
    return post_retrieval.make_post_retrieval_processor(name)


@functools.lru_cache(maxsize=8)
def build_reranker(name: str):
    """Construct a Reranker implementation (lazy import of rerank module)."""
    from rag import rerank  # noqa: WPS433
    return rerank.make_reranker(name)


@functools.lru_cache(maxsize=8)
def build_cache(name: str):
    """Construct a Cache implementation (lazy import of cache module).

    Cached by name so the same variant reuses one stateful cache instance across
    requests within a process (Req 18).
    """
    from rag import cache as cache_module  # noqa: WPS433
    return cache_module.make_cache(name)


@functools.lru_cache(maxsize=8)
def build_guardrail(name: str):
    """Construct a Guardrail implementation (lazy import of guardrails module)."""
    from rag import guardrails  # noqa: WPS433
    return guardrails.make_guardrail(name)


@functools.lru_cache(maxsize=1)
def build_access_policy_provider(name: str = "in_memory_sqlite"):
    """Construct the shared AccessPolicyProvider (lazy import of governance module).

    Cached as a singleton so Access_Policies persist across requests (Req 11.16).
    """
    from rag import governance  # noqa: WPS433
    return governance.InMemoryAccessPolicyProvider()


@functools.lru_cache(maxsize=4)
def build_orchestrator(name: str):
    """Construct an Orchestrator implementation (lazy import of orchestrator module)."""
    from rag import orchestrator  # noqa: WPS433
    return orchestrator.make_orchestrator(name)


@functools.lru_cache(maxsize=4)
def build_evaluation_framework(name: str):
    """Construct an EvaluationFramework implementation (lazy import of evaluation module)."""
    from rag import evaluation  # noqa: WPS433
    return evaluation.make_evaluation_framework(name)
