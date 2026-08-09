"""Structured error envelope + exception handlers (Req 14.1, 14.3-14.7, 24.2, 24.5).

Every error response has the shape ``{"error": {"code", "message", "module", "variant"}}``.
Provider-failure errors name the failing module and the provider's message but never
an Env_Key value (the underlying exceptions never carry one, by construction — see
``rag.generate``/``rag.rerank``). Auth errors are registered as their own handler so
FastAPI dispatches them ahead of any handler for generic/data errors (Req 14.6, 14.7).
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.deps import AuthError
from rag.evaluation import EvaluationError
from rag.generate import GenerationProviderError
from rag.generate import MissingApiKeyError as GenMissingApiKeyError
from rag.persistence import DuplicateVariantNameError, PersistenceError, VariantNotFoundError
from rag.pipeline import ConversationNotFoundError, IndexNotBuiltError, NoDocumentsIngestedError, UnknownVariantError
from rag.rerank import MissingApiKeyError as RerankMissingApiKeyError


def error_envelope(code: str, message: str, module: str | None = None, variant: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "module": module, "variant": variant}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def _auth_error(request: Request, exc: AuthError):
        return JSONResponse(status_code=401, content=error_envelope("UNAUTHENTICATED", str(exc)))

    @app.exception_handler(UnknownVariantError)
    async def _unknown_variant(request: Request, exc: UnknownVariantError):
        return JSONResponse(status_code=404, content=error_envelope("UNKNOWN_VARIANT", str(exc), variant=exc.name))

    @app.exception_handler(IndexNotBuiltError)
    async def _index_not_built(request: Request, exc: IndexNotBuiltError):
        return JSONResponse(status_code=409, content=error_envelope("INDEX_NOT_BUILT", str(exc), variant=exc.name))

    @app.exception_handler(NoDocumentsIngestedError)
    async def _no_documents(request: Request, exc: NoDocumentsIngestedError):
        return JSONResponse(status_code=409, content=error_envelope("NO_DOCUMENTS_INGESTED", str(exc)))

    @app.exception_handler(DuplicateVariantNameError)
    async def _duplicate_variant(request: Request, exc: DuplicateVariantNameError):
        return JSONResponse(status_code=409, content=error_envelope("DUPLICATE_VARIANT_NAME", str(exc), variant=exc.name))

    @app.exception_handler(VariantNotFoundError)
    async def _variant_not_found(request: Request, exc: VariantNotFoundError):
        return JSONResponse(status_code=404, content=error_envelope("VARIANT_NOT_FOUND", str(exc), variant=exc.name))

    @app.exception_handler(ConversationNotFoundError)
    async def _conversation_not_found(request: Request, exc: ConversationNotFoundError):
        return JSONResponse(status_code=404, content=error_envelope("CONVERSATION_NOT_FOUND", str(exc)))

    @app.exception_handler(PersistenceError)
    async def _persistence_error(request: Request, exc: PersistenceError):
        return JSONResponse(
            status_code=500, content=error_envelope("PERSISTENCE_ERROR", str(exc), module=exc.operation)
        )

    @app.exception_handler(GenMissingApiKeyError)
    async def _gen_missing_key(request: Request, exc: GenMissingApiKeyError):
        return JSONResponse(
            status_code=424, content=error_envelope("MISSING_API_KEY", str(exc), module=exc.module)
        )

    @app.exception_handler(RerankMissingApiKeyError)
    async def _rerank_missing_key(request: Request, exc: RerankMissingApiKeyError):
        return JSONResponse(
            status_code=424, content=error_envelope("MISSING_API_KEY", str(exc), module=exc.module)
        )

    @app.exception_handler(GenerationProviderError)
    async def _provider_error(request: Request, exc: GenerationProviderError):
        return JSONResponse(
            status_code=502, content=error_envelope("PROVIDER_ERROR", str(exc), module=exc.module)
        )

    @app.exception_handler(EvaluationError)
    async def _evaluation_error(request: Request, exc: EvaluationError):
        return JSONResponse(
            status_code=502, content=error_envelope("EVALUATION_ERROR", str(exc), module=exc.framework)
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content=error_envelope("INVALID_REQUEST", str(exc)))

    @app.exception_handler(Exception)
    async def _generic_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content=error_envelope("INTERNAL_ERROR", str(exc)))


# ---------------------------------------------------------------------------
# Response serialization helpers
# ---------------------------------------------------------------------------

def serialize_answer_result(result) -> dict:
    return asdict(result)


def serialize_trace(trace) -> dict:
    return asdict(trace)


def serialize_metric_scores(result) -> dict:
    return {
        "scores": result.scores,
        "passed": result.passed,
        "reasons": result.reasons,
        "excluded_reference_dependent": result.excluded_reference_dependent,
    }


def serialize_retrieval_metrics(result) -> dict:
    return {
        "overall": result.overall,
        "by_query_type": result.by_query_type,
    }
