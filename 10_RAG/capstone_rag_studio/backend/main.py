"""RAG Studio FastAPI backend — the REST/JSON surface over :mod:`rag.pipeline`.

Every route depends on ``get_principal`` first (Req 14.3, 14.6, 14.7) and a shared
``RagStudioPipeline`` second. ``create_app`` is a factory so tests (and anything else
that wants an isolated pipeline/db) can build their own app instance; ``app`` is the
default instance uvicorn imports.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.deps import get_principal
from backend.errors import (
    install_error_handlers,
    serialize_answer_result,
    serialize_metric_scores,
    serialize_retrieval_metrics,
    serialize_trace,
)
from rag.config import PipelineConfig
from rag.interfaces import AccessPolicy, Principal
from rag.pipeline import RagStudioPipeline, UnknownVariantError

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"   # backend/main.py -> capstone_rag_studio -> 10_RAG/.env
load_dotenv(_ENV_PATH, override=False)   # load Env_Keys at startup (Req 13.9)

_OPTIONAL_ENV_KEYS = ("OPENROUTER_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY")


def create_app(pipeline: Optional[RagStudioPipeline] = None) -> FastAPI:
    app = FastAPI(title="RAG Studio")

    cors_origins = [
        o.strip() for o in os.getenv("RAG_STUDIO_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    _holder: dict[str, Optional[RagStudioPipeline]] = {"pipeline": pipeline}

    def get_pipeline() -> RagStudioPipeline:
        if _holder["pipeline"] is None:
            _holder["pipeline"] = RagStudioPipeline(
                db_path=os.getenv("RAG_STUDIO_DB_PATH", "./rag_studio.sqlite"),
                upload_dir=os.getenv("RAG_STUDIO_UPLOAD_DIR", "./uploads"),
            )
        return _holder["pipeline"]

    # --- health (Req 14.4 no-auth-required readiness check) ---

    @app.get("/health")
    def health():
        warnings = []
        if not os.getenv("OPENAI_API_KEY"):
            warnings.append("OPENAI_API_KEY is not set — core embedding/generation features are unavailable.")
        for key in _OPTIONAL_ENV_KEYS:
            if not os.getenv(key):
                warnings.append(f"{key} is not set — dependent options are unavailable.")
        return {"status": "ok", "warnings": warnings}

    # --- options (Req 1) ---

    @app.get("/options")
    def get_options(principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)):
        return pipeline.build_options_catalog()

    # --- variants (Req 2) ---

    @app.get("/variants")
    def list_variants(principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)):
        return {name: cfg.to_dict() for name, cfg in pipeline.list_variants().items()}

    @app.post("/variants")
    def save_variant(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        config = PipelineConfig.normalize(payload)
        pipeline.save_variant(config)
        return {"status": "saved", "name": config.name}

    @app.delete("/variants/{name}")
    def delete_variant(
        name: str, principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)
    ):
        pipeline.delete_variant(name)
        return {"status": "deleted", "name": name}

    # --- ingest + index (Req 3, 4) ---

    @app.post("/ingest")
    async def ingest(
        files: list[UploadFile] = File(...),
        access_level: str = Form("PRIVATE"),
        acl: str = Form(""),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        acl_list = [a.strip() for a in acl.split(",") if a.strip()]
        policy = AccessPolicy(access_level=access_level, owner=principal.id, acl=acl_list)
        saved_files = []
        for uploaded in files:
            content = await uploaded.read()
            path = pipeline._store.save_upload(uploaded.filename, content)
            saved_files.append({"path": path, "source": uploaded.filename})
        docs = pipeline.ingest_documents(saved_files, policy)
        return {"ingested": [d["source"] for d in docs]}

    @app.post("/index")
    def build_index(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        variant_name = payload.get("variant_name")
        if not variant_name:
            raise ValueError("'variant_name' is required.")
        variants = pipeline.list_variants()
        if variant_name not in variants:
            raise UnknownVariantError(variant_name)
        result = pipeline.build_index(variants[variant_name], pipeline.all_docs())
        return {"status": "indexed", "variant_name": variant_name, "chunk_count": len(result.chunks)}

    # --- chat & compare (Req 5, 6) ---

    @app.post("/chat")
    def chat(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        question = payload.get("question")
        if not question:
            raise ValueError("'question' is required.")
        variant_names = payload.get("variant_names")
        configs = pipeline.resolve_variants_for_chat(variant_names)
        outcome = pipeline.run_all_variants(configs, question, principal)
        return {
            "results": {name: serialize_answer_result(r) for name, r in outcome.results.items()},
            "errors": outcome.errors,
        }

    @app.get("/trace/{request_id}")
    def get_trace(
        request_id: str, principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)
    ):
        trace = pipeline.get_trace(request_id)
        if trace is None:
            raise ValueError(f"No trace found for request id '{request_id}'.")
        return serialize_trace(trace)

    # --- conversational chat (multi-turn, sliding-window memory) ---

    @app.get("/conversations")
    def list_conversations(
        principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)
    ):
        return pipeline.list_conversations(principal)

    @app.post("/conversations")
    def start_conversation(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        variant_name = payload.get("variant_name")
        if not variant_name:
            raise ValueError("'variant_name' is required.")
        conversation_id = pipeline.start_conversation(principal, variant_name)
        return {"conversation_id": conversation_id, "variant_name": variant_name}

    @app.get("/conversations/{conversation_id}/messages")
    def get_conversation_messages(
        conversation_id: str,
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        return {"messages": pipeline.get_conversation_history(principal, conversation_id)}

    @app.post("/conversations/{conversation_id}/messages")
    def post_conversation_message(
        conversation_id: str,
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        content = payload.get("content")
        if not content:
            raise ValueError("'content' is required.")
        result = pipeline.send_message(principal, conversation_id, content)
        return serialize_answer_result(result)

    # --- evaluation (Req 7, 8) ---

    @app.post("/evaluate/live")
    def evaluate_live(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        samples = payload.get("samples", [])
        framework = payload.get("framework", "ragas")
        metrics = payload.get("metrics", ["faithfulness", "answer_relevancy"])
        result = pipeline.evaluate_live(samples, framework, metrics)
        return serialize_metric_scores(result)

    @app.post("/evaluate/golden")
    def evaluate_golden(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        samples = payload.get("samples", [])
        framework = payload.get("framework", "ragas")
        metrics = payload.get("metrics", ["faithfulness", "answer_relevancy", "context_precision", "context_recall"])
        result = pipeline.evaluate_golden(samples, framework, metrics)
        return serialize_metric_scores(result)

    @app.post("/evaluate/retrieval")
    def evaluate_retrieval(
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        golden_set = payload.get("golden_set", [])
        variant_names = payload.get("variant_names") or None
        results, errors = pipeline.evaluate_retrieval(golden_set, variant_names, principal)
        return {
            "results": {name: serialize_retrieval_metrics(r) for name, r in results.items()},
            "errors": errors,
        }

    # --- governance (Req 11.11, 11.12) ---

    @app.get("/governance/policy/{doc_id}")
    def get_policy(
        doc_id: str, principal: Principal = Depends(get_principal), pipeline: RagStudioPipeline = Depends(get_pipeline)
    ):
        policy = pipeline.get_access_policy(doc_id)
        return {"access_level": policy.access_level, "owner": policy.owner, "acl": policy.acl}

    @app.post("/governance/policy/{doc_id}")
    def set_policy(
        doc_id: str,
        payload: dict = Body(default={}),
        principal: Principal = Depends(get_principal),
        pipeline: RagStudioPipeline = Depends(get_pipeline),
    ):
        policy = AccessPolicy(
            access_level=payload.get("access_level", "PRIVATE"),
            owner=payload.get("owner", principal.id),
            acl=payload.get("acl", []),
        )
        pipeline.set_access_policy(doc_id, policy)
        return {"status": "updated", "doc_id": doc_id}

    return app


app = create_app()
