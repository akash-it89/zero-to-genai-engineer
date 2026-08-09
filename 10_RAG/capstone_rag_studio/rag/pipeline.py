"""Transport-agnostic pipeline façade — the single entry point higher layers use.

Not itself a "stage module" (Req 12.6): this is the one place allowed to import every
stage module and wire concrete collaborators together for a given ``PipelineConfig``,
so the FastAPI backend and the capstone notebook only ever call these functions
(Req 11.2). Configs are validated against the Registry before every save/run
(Req 2.6).
"""
from __future__ import annotations

import uuid
from typing import Optional

from rag import governance, ingest, registry
from rag.config import PipelineConfig
from rag.interfaces import (
    AccessPolicy,
    AnswerResult,
    ConversationTurn,
    MetricScores,
    PipelineContext,
    Principal,
    RetrievalMetricScores,
    Trace,
    source_prefixed_text,
)
from rag.persistence import SqlitePersistence
from rag.retrieval_metrics import score_retrieval

CONVERSATION_MEMORY_WINDOW = 6   # last N messages (sliding window) sent to the LLM each turn


class VariantRunResult:
    """Results of running many variants, with per-variant failure isolation
    (Req 6.4, 14.2, P17): ``len(results) + len(errors) == len(configs)`` always."""

    def __init__(self, results: dict[str, AnswerResult], errors: dict[str, str]):
        self.results = results
        self.errors = errors


class UnknownVariantError(Exception):
    """Raised when a request names a variant that has never been saved (Req 14.4, 14.5)."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Unknown variant: '{name}'.")


class IndexNotBuiltError(Exception):
    """Raised when a variant exists but no index has been built for it yet (Req 14.4, 14.5)."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"No index has been built yet for variant '{name}'.")


class NoDocumentsIngestedError(Exception):
    """Raised in place of Unknown_Variant/Index_Not_Built when nothing has ever been
    ingested — the ingestion error is preferred when both conditions would otherwise
    hold (Req 14.4, 14.5)."""

    def __init__(self):
        super().__init__("No documents have been ingested yet.")


class ConversationNotFoundError(Exception):
    """Raised when a conversation id doesn't exist or doesn't belong to the acting
    principal (the two are treated identically — never reveal that a conversation
    exists under a different principal)."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        super().__init__(f"No conversation found with id '{conversation_id}'.")


class RagStudioPipeline:
    """The top-level façade (Req 11.2)."""

    def __init__(self, db_path: str = "./rag_studio.sqlite", upload_dir: str = "./uploads"):
        self._store = SqlitePersistence(db_path=db_path, upload_dir=upload_dir)
        self._access_provider = governance.InMemoryAccessPolicyProvider()
        self._audit_sink = governance.InMemoryAuditLog()
        self._indexes: dict[str, dict] = {}   # variant name -> {"embedder","vector_store","all_chunks"}
        self._traces: dict[str, Trace] = {}
        self._docs: list[dict] = []           # accumulated ingested docs, ready for build_index

    # --- Options catalog (Req 1) ---

    def build_options_catalog(self) -> dict:
        return registry.options_snapshot()

    # --- Variant CRUD (Req 2.1-2.4, 2.6) ---

    def save_variant(self, config: PipelineConfig) -> None:
        errors = registry.validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        self._store.save_variant(config.name, config.to_dict())

    def list_variants(self) -> dict[str, PipelineConfig]:
        return {name: PipelineConfig.normalize(cfg) for name, cfg in self._store.list_variants().items()}

    def delete_variant(self, name: str) -> None:
        self._store.delete_variant(name)

    # --- Ingestion + indexing (Req 3, 11.1, 11.16) ---

    def ingest_documents(self, files: list[dict], access_policy: AccessPolicy) -> list[dict]:
        """``files``: ``[{"path": str, "source": optional str}]``.

        Loads clean text for each file, attaches ``access_policy`` to it, and durably
        + live-registers that policy under the file's ``source`` doc id. Returns doc
        dicts ready for :meth:`build_index`.
        """
        docs = []
        for f in files:
            path = f["path"]
            source = f.get("source", path)
            text = ingest.load_file(path)
            docs.append({"text": text, "source": source, "access_policy": access_policy})
            self._store.set_access_policy(source, access_policy)
            self._access_provider.set_policy(source, access_policy)
        self._docs.extend(docs)
        return docs

    def all_docs(self) -> list[dict]:
        return list(self._docs)

    def build_index(self, config: PipelineConfig, docs: list[dict]):
        """Chunk -> embed -> index the given docs for one variant (Req 3, 4.1)."""
        result = ingest.build_chunks(
            docs, strategy=config.chunk_strategy, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )
        embedder = registry.build_embedder(config.embedding)
        vector_store = registry.build_vector_store(
            config.vector_store, dim=embedder.dim,
            persist_dir=f".chroma_{config.name}", index_name=config.name,
        )
        if result.chunks:
            # Embed source-prefixed text (not raw c.text) so semantic search carries a
            # document-identity signal — otherwise a chunk from the *wrong* document
            # that happens to discuss the right one by name embeds deceptively close
            # to the query (see rag.interfaces.source_prefixed_text).
            vectors = embedder.embed_documents([source_prefixed_text(c) for c in result.chunks])
            ids = [c.id for c in result.chunks]
            vector_store.add(ids, vectors, result.chunks)
            vector_store.persist()
        self._indexes[config.name] = {
            "embedder": embedder,
            "vector_store": vector_store,
            "all_chunks": result.chunks,
        }
        return result

    # --- Running variants (Req 5, 6, 21) ---

    def _build_context(
        self,
        config: PipelineConfig,
        principal: Principal,
        request_id: str,
        history: Optional[list[ConversationTurn]] = None,
    ) -> PipelineContext:
        index = self._indexes.get(config.name)
        embedder = index["embedder"] if index else registry.build_embedder(config.embedding)
        vector_store = (
            index["vector_store"] if index
            else registry.build_vector_store(config.vector_store, dim=embedder.dim)
        )
        all_chunks = index["all_chunks"] if index else []
        generation_llm = registry.build_llm(config.llm, config.temperature)

        extras = {
            "cache": registry.build_cache(config.caching),
            "guardrail": registry.build_guardrail(config.guardrails),
            "retriever": registry.build_retriever(config.retrieval),
            "query_transformer": registry.build_query_transformer(config.query_transform),
            "post_retrieval_processor": registry.build_post_retrieval_processor(config.post_retrieval),
            "reranker": registry.build_reranker(config.reranker),
            "governance_filter": governance.GovernanceFilter(self._access_provider),
            "audit_sink": self._audit_sink,
            "all_chunks": all_chunks,
            "traces": self._traces,
            "history": history,   # prior conversation turns — None for stateless single-shot calls
        }
        return PipelineContext(
            config=config, principal=principal, request_id=request_id,
            embedder=embedder, vector_store=vector_store, generation_llm=generation_llm,
            access_provider=self._access_provider, extras=extras,
        )

    def run_variant(
        self,
        config: PipelineConfig,
        question: str,
        principal: Principal,
        history: Optional[list[ConversationTurn]] = None,
    ) -> AnswerResult:
        errors = registry.validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        request_id = str(uuid.uuid4())
        ctx = self._build_context(config, principal, request_id, history=history)
        orchestrator = registry.build_orchestrator(config.orchestrator)
        return orchestrator.run(config, question, principal, ctx)

    def run_all_variants(self, configs: list[PipelineConfig], question: str, principal: Principal) -> VariantRunResult:
        results: dict[str, AnswerResult] = {}
        errors: dict[str, str] = {}
        for config in configs:
            try:
                results[config.name] = self.run_variant(config, question, principal)
            except Exception as exc:   # per-variant isolation (Req 6.4, 14.2, P17)
                errors[config.name] = str(exc)
        return VariantRunResult(results, errors)

    def resolve_variants_for_chat(self, variant_names: Optional[list[str]] = None) -> list[PipelineConfig]:
        """Resolve the configs a /chat request should run against (Req 6.1, 6.4).

        Raises :class:`NoDocumentsIngestedError` in place of Unknown_Variant/
        Index_Not_Built whenever nothing has ever been ingested — that is the more
        fundamental missing prerequisite, so it is preferred when both conditions
        would otherwise hold (Req 14.4, 14.5).
        """
        saved = self.list_variants()
        has_docs = bool(self._docs)

        if variant_names is None:
            if not saved:
                if not has_docs:
                    raise NoDocumentsIngestedError()
                raise ValueError("No strategy variants have been saved yet.")
            variant_names = list(saved.keys())

        configs = []
        for name in variant_names:
            if name not in saved:
                if not has_docs:
                    raise NoDocumentsIngestedError()
                raise UnknownVariantError(name)
            if name not in self._indexes:
                if not has_docs:
                    raise NoDocumentsIngestedError()
                raise IndexNotBuiltError(name)
            configs.append(saved[name])
        return configs

    # --- Conversational chat (multi-turn, sliding-window memory, SQLite-persisted) ---

    def start_conversation(self, principal: Principal, variant_name: str) -> str:
        """Creates a new conversation thread against one variant. The variant must
        already be saved and indexed (same prerequisites as any chat run)."""
        configs = self.resolve_variants_for_chat([variant_name])
        variant_name = configs[0].name
        conversation_id = str(uuid.uuid4())
        self._store.create_conversation(conversation_id, variant_name, principal.id)
        return conversation_id

    def list_conversations(self, principal: Principal) -> list[dict]:
        return self._store.list_conversations(principal.id)

    def get_conversation_history(self, principal: Principal, conversation_id: str) -> list[dict]:
        self._require_owned_conversation(principal, conversation_id)
        return self._store.list_conversation_messages(conversation_id)

    def _require_owned_conversation(self, principal: Principal, conversation_id: str) -> dict:
        conversation = self._store.get_conversation(conversation_id)
        if conversation is None or conversation["principal_id"] != principal.id:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    def send_message(self, principal: Principal, conversation_id: str, message: str) -> AnswerResult:
        """Runs one conversational turn: loads the last CONVERSATION_MEMORY_WINDOW
        messages as sliding-window memory, runs the variant with that history, then
        persists both the user message and the cited assistant reply."""
        conversation = self._require_owned_conversation(principal, conversation_id)
        configs = self.resolve_variants_for_chat([conversation["variant_name"]])
        config = configs[0]

        prior_messages = self._store.list_conversation_messages(conversation_id)
        windowed = prior_messages[-CONVERSATION_MEMORY_WINDOW:]
        history = [ConversationTurn(role=m["role"], content=m["content"]) for m in windowed]

        self._store.append_conversation_message(conversation_id, "user", message)
        result = self.run_variant(config, message, principal, history=history)

        citations = [{"chunk_id": c.chunk_id, "source": c.source} for c in result.citations]
        self._store.append_conversation_message(
            conversation_id, "assistant", result.answer, citations=citations, trace_id=result.trace_id
        )
        return result

    # --- Evaluation (Req 7, 8) ---

    def evaluate_live(self, samples: list[dict], framework_name: str, metrics: list[str]) -> MetricScores:
        framework = registry.build_evaluation_framework(framework_name)
        return framework.evaluate(samples, metrics, reference=False)

    def evaluate_golden(self, samples: list[dict], framework_name: str, metrics: list[str]) -> MetricScores:
        framework = registry.build_evaluation_framework(framework_name)
        return framework.evaluate(samples, metrics, reference=True)

    def evaluate_retrieval(
        self,
        golden_set: list[dict],
        variant_names: Optional[list[str]],
        principal: Principal,
    ) -> tuple[dict[str, RetrievalMetricScores], dict[str, str]]:
        """Scores retrieval-stage ablation metrics (R@1/R@3/MRR@10/NDCG@3) for each
        resolved variant against ``golden_set`` (student capstone requirement — see
        ``student_group_datasets/EVALUATION_METHODOLOGY.md``).

        ``golden_set`` items: ``{"question": str, "expected_sources": list[str],
        "query_type": optional str}``. Runs the real pipeline per golden question,
        identically to :meth:`run_variant` under ``/chat``, and reads off each
        result's ranked chunk sources — scores reflect exactly what the chatbot
        would have retrieved, not a synthetic retrieval-only shortcut. Per-variant
        failure isolation matches :meth:`run_all_variants` (Req 6.4, 14.2, P17).
        """
        configs = self.resolve_variants_for_chat(variant_names)
        results: dict[str, RetrievalMetricScores] = {}
        errors: dict[str, str] = {}

        for config in configs:
            try:
                per_query_ranked: list[list[str]] = []
                per_query_expected: list[list[str]] = []
                per_query_type: list[Optional[str]] = []
                for item in golden_set:
                    question = item["question"]
                    answer_result = self.run_variant(config, question, principal)
                    chunks = answer_result.reranked_chunks or answer_result.retrieved_chunks
                    per_query_ranked.append([c.source for c in chunks])
                    per_query_expected.append(item.get("expected_sources", []))
                    per_query_type.append(item.get("query_type"))
                results[config.name] = score_retrieval(per_query_ranked, per_query_expected, per_query_type)
            except Exception as exc:   # per-variant isolation (Req 6.4, 14.2, P17)
                errors[config.name] = str(exc)

        return results, errors

    # --- Trace + governance (Req 11.11, 11.12, 19.2) ---

    def get_trace(self, request_id: str) -> Optional[Trace]:
        return self._traces.get(request_id)

    def get_access_policy(self, doc_id: str) -> AccessPolicy:
        return self._access_provider.get_policy(doc_id)

    def set_access_policy(self, doc_id: str, policy: AccessPolicy) -> None:
        self._store.set_access_policy(doc_id, policy)
        self._access_provider.set_policy(doc_id, policy)
