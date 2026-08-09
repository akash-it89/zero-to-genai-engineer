"""Stage interfaces (ABCs) and core domain dataclasses for RAG Studio.

This is the ONLY module (besides :mod:`rag.registry` and :mod:`rag.config`) that
stage implementations may import from. It defines:

* the abstract ``Stage_Interface`` for every pipeline module, and
* the plain dataclasses passed between stages.

Everything here is provider-agnostic pure Python so the package can be imported and
unit-tested without FastAPI or any provider SDK installed (Req 10.1, 12.1, 12.2, 12.6).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Optional, Sequence

if TYPE_CHECKING:  # avoid a hard numpy dependency in type-only positions
    import numpy as np

    Vector = "np.ndarray"
else:
    Vector = Any


# ---------------------------------------------------------------------------
# Access-control model (Req 11)
# ---------------------------------------------------------------------------

Access_Level = Literal["PUBLIC", "RESTRICTED", "PRIVATE"]


@dataclass
class AccessPolicy:
    """The complete access specification attached to a document (Req 11.1, 11.2)."""

    access_level: Access_Level = "PRIVATE"   # default when unspecified (Req 11.2)
    owner: str = ""                          # Acting_Principal at ingest time (Req 11.1)
    acl: list[str] = field(default_factory=list)  # User/Role/Group ids granted access


@dataclass
class Principal:
    """An identified actor whose access rights are evaluated (Req 11 glossary)."""

    id: str
    kind: Literal["user", "role", "group"] = "user"
    roles: list[str] = field(default_factory=list)  # groups/roles this principal belongs to

    def identities(self) -> set[str]:
        """All ids this principal matches against an ACL: itself plus its roles/groups."""
        return {self.id, *self.roles}


# ---------------------------------------------------------------------------
# Pipeline payload dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A unit of indexed text with an inherited access policy (Req 3.5)."""

    id: str
    text: str
    source: str                                # source document id
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)


def source_prefixed_text(chunk: Chunk) -> str:
    """``chunk.text`` prefixed with a readable title derived from ``chunk.source``.

    Embedding/BM25/reranking otherwise score chunk text blind to which document it
    came from. Two documents can both discuss the same named entity (e.g. a later
    paper's related-work section mentions an earlier model by name repeatedly while
    benchmarking against it), so a passage from the *wrong* document can out-score
    the right document's own best passage on pure text relevance — verified against
    the actual GPT-2/GPT-3 papers: without this, only 1/8 fused retrieval candidates
    for "overview of GPT-2" came from the GPT-2 paper itself. Used at every stage that
    scores chunk text against a query (dense embedding, BM25, rerank) without ever
    mutating ``chunk.text`` — citations and generation still see the original text.
    """
    import re

    title = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", chunk.source)   # strip file extension
    title = re.sub(r"[_\-]+", " ", title).strip()
    return f"{title}: {chunk.text}" if title else chunk.text


@dataclass
class Candidate:
    """A retrieved chunk with its first-stage score and rank."""

    chunk: Chunk
    score: float
    rank: int


@dataclass
class QueryPlan:
    """Output of a QueryTransformer: the queries to actually retrieve for.

    ``queries`` is the list of (possibly transformed) query strings; ``embed_texts``
    optionally overrides what gets embedded (e.g. a HyDE hypothetical document).
    ``merge`` signals that per-query candidate sets should be merged/de-duplicated.
    """

    queries: list[str]
    embed_texts: Optional[list[str]] = None
    merge: bool = False


@dataclass
class Citation:
    """A reference in an answer to a supporting source chunk (Req 5.2, 5.6)."""

    chunk_id: str
    source: str


@dataclass
class GenerationOutput:
    """Raw output of a GenerationLLM before AnswerResult assembly."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    token_usage: int = 0
    cost_estimate: float = 0.0


@dataclass
class ConversationTurn:
    """One prior turn of a multi-turn conversation, fed back to the LLM as real
    chat message history (Req: conversational chat memory)."""

    role: Literal["user", "assistant"]
    content: str


@dataclass
class AnswerResult:
    """The full result of running one question through one variant (Req 5.4)."""

    variant_name: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    retrieved_chunks: list[Chunk] = field(default_factory=list)
    reranked_chunks: list[Chunk] = field(default_factory=list)
    per_stage_timing: dict[str, float] = field(default_factory=dict)
    governance_filtered_count: int = 0         # count only, never content (Req 11.14)
    trace_id: str = ""
    no_accessible_context: bool = False        # Req 11.15


@dataclass
class GuardrailVerdict:
    """Result of an input/output guardrail screen (Req 20)."""

    allowed: bool = True
    flagged: bool = False
    reason: str = ""
    text: str = ""                             # possibly-redacted content


# ---------------------------------------------------------------------------
# Observability (Req 19)
# ---------------------------------------------------------------------------

@dataclass
class StageTrace:
    stage: str
    input_size: int = 0
    elapsed_ms: float = 0.0
    token_usage: int = 0                       # 0 for local modules (Req 19.4)
    cost_estimate: float = 0.0                 # 0.0 for local modules (Req 19.4)


@dataclass
class Trace:
    request_id: str
    variant_name: str
    stages: list[StageTrace] = field(default_factory=list)
    total_token_usage: int = 0
    total_cost_estimate: float = 0.0
    governance_filtered_count: int = 0
    # NOTE: never contains removed-chunk content or Env_Key values (Req 19.6)


@dataclass
class MetricScores:
    """Evaluation output: metric -> score, plus optional pass/fail and reasons."""

    scores: dict[str, float] = field(default_factory=dict)
    passed: dict[str, bool] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    excluded_reference_dependent: list[str] = field(default_factory=list)  # Req 8.8


@dataclass
class RetrievalMetricScores:
    """Retrieval-stage ablation output: R@1/R@3/MRR@10/NDCG@3, overall and (when the
    golden set carries a ``query_type`` per item) broken out per query type — see
    :mod:`rag.retrieval_metrics`."""

    overall: dict[str, float] = field(default_factory=dict)
    by_query_type: dict[str, dict[str, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage interfaces (ABCs) — Req 12.1
# ---------------------------------------------------------------------------

class Parser(ABC):
    """File -> clean text (Req 3.1-3.3)."""

    extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: str) -> str: ...


class Chunker(ABC):
    """Clean text -> list of chunk strings (Req 3.4)."""

    @abstractmethod
    def split(self, text: str, size: int, overlap: int) -> list[str]: ...


class Embedder(ABC):
    """Text -> dense vectors. ``is_local`` gates cost accounting (Req 19.4, 22.3)."""

    dim: int = 0
    is_local: bool = False

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> Vector: ...

    def embed_query(self, text: str) -> Vector:
        return self.embed_documents([text])[0]


class VectorStore(ABC):
    """Holds embeddings and answers similarity search (Req 4.1)."""

    @abstractmethod
    def add(self, ids: Sequence[str], vectors: Vector, chunks: Sequence[Chunk]) -> None: ...

    @abstractmethod
    def search(self, query_vec: Vector, k: int) -> list[Candidate]: ...

    def persist(self) -> None:  # overridden by Chroma (Req 23.4)
        return None


class Retriever(ABC):
    """Candidate selection for a query (Req 4.1-4.4)."""

    mode: str = ""   # dense | bm25 | hybrid_rrf | hybrid_weighted

    @abstractmethod
    def retrieve(self, query: str, top_k: int, ctx: "PipelineContext") -> list[Candidate]: ...


class QueryTransformer(ABC):
    """Pre-retrieval query rewriting/expansion (Req 16)."""

    @abstractmethod
    def transform(self, question: str, ctx: "PipelineContext") -> QueryPlan: ...


class PostRetrievalProcessor(ABC):
    """Runs after governance filtering, before rerank/generation (Req 17). Only removes."""

    @abstractmethod
    def process(self, question: str, chunks: list[Chunk], ctx: "PipelineContext") -> list[Chunk]: ...


class Reranker(ABC):
    """Reorders governance-filtered candidates (Req 4.6, 4.7)."""

    is_local: bool = True

    @abstractmethod
    def rerank(self, question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]: ...


class GenerationLLM(ABC):
    """Produces the final grounded, cited answer (Req 5).

    ``history`` carries prior conversation turns (already sliding-window-bounded by
    the caller) for conversational chat; it is ``None``/empty for a stateless
    single-shot call (e.g. Chat & Compare), which behaves exactly as before.
    """

    @abstractmethod
    def generate(
        self, question: str, context_chunks: list[Chunk], history: Optional[list[ConversationTurn]] = None
    ) -> GenerationOutput: ...


class Cache(ABC):
    """Cross-cutting result cache, principal+config scoped (Req 18)."""

    @abstractmethod
    def key(self, principal: Principal, config_dict: dict, question: str) -> str: ...

    @abstractmethod
    def get(self, key: str) -> Optional[AnswerResult]: ...

    @abstractmethod
    def put(self, key: str, result: AnswerResult) -> None: ...


class Guardrail(ABC):
    """Cross-cutting input/output screening (Req 20)."""

    @abstractmethod
    def screen_input(self, question: str) -> GuardrailVerdict: ...

    @abstractmethod
    def screen_output(self, answer: str) -> GuardrailVerdict: ...


class Orchestrator(ABC):
    """Composes the stage pipeline for a variant (Req 21)."""

    @abstractmethod
    def run(self, config, question: str, principal: Principal, ctx: "PipelineContext") -> AnswerResult: ...


class EvaluationFramework(ABC):
    """RAGAS or DeepEval metric computation (Req 7, 8)."""

    @abstractmethod
    def evaluate(self, samples: list[dict], metrics: list[str], reference: bool = False) -> MetricScores: ...


class AccessPolicyProvider(ABC):
    """Stores Access_Policies and answers authorization decisions (Req 11.16)."""

    @abstractmethod
    def get_policy(self, doc_id: str) -> AccessPolicy: ...

    @abstractmethod
    def set_policy(self, doc_id: str, policy: AccessPolicy) -> None: ...

    @abstractmethod
    def is_authorized(self, principal: Principal, doc_id: str) -> bool: ...


# ---------------------------------------------------------------------------
# Shared context handed to stages during a single run
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Everything a stage may need for one run, assembled by the façade/orchestrator.

    Holds already-constructed collaborators (embedder, vector store, generation LLM,
    access-policy provider) plus the immutable request inputs. Stages read from this
    rather than importing each other, preserving module isolation (Req 12.6).
    """

    config: Any                                # PipelineConfig (avoids import cycle)
    principal: Principal
    request_id: str = ""
    embedder: Optional[Embedder] = None
    vector_store: Optional[VectorStore] = None
    generation_llm: Optional[GenerationLLM] = None
    access_provider: Optional[AccessPolicyProvider] = None
    extras: dict = field(default_factory=dict)
