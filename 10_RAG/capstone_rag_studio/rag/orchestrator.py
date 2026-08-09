"""Linear_Flow orchestrator: composes the full stage pipeline for one variant (Req 21).

Only imports :mod:`rag.interfaces` (module isolation, Req 12.6) — every collaborator
(retriever, query transformer, post-retrieval processor, reranker, cache, guardrail,
governance filter, audit sink) is handed in through ``ctx.extras`` by the façade
(``rag.pipeline``), which is the one module allowed to import every stage module and
wire them together for a given ``PipelineConfig`` (Req 21.1-21.3). The stage sequence
runs exactly once, in a fixed order, with no branching or looping (Req 21.1).
"""
from __future__ import annotations

import time

from rag.interfaces import (
    AnswerResult,
    Candidate,
    GuardrailVerdict,
    Orchestrator,
    Principal,
    StageTrace,
    Trace,
)

NO_CONTEXT_MESSAGE = "No accessible context was found for your question."

# The canonical, fixed stage order every request follows (Req 21.1, P19).
CANONICAL_STAGE_ORDER = [
    "input_guardrail",
    "query_transform",
    "retrieval",
    "governance",
    "post_retrieval",
    "rerank",
    "generate",
    "output_guardrail",
]


def _merge_candidates(per_query_results: list[list[Candidate]], top_k: int) -> list[Candidate]:
    """De-duplicates multi-query candidate sets to the set-union of chunk ids, keeping
    each chunk's best score (Req 16.4, P18). Reimplemented locally (rather than
    imported from rag.retrieval) since orchestrator may not import a sibling stage
    module's internals (Req 12.6)."""
    best: dict[str, Candidate] = {}
    for results in per_query_results:
        for cand in results:
            cid = cand.chunk.id
            if cid not in best or cand.score > best[cid].score:
                best[cid] = cand
    ordered = sorted(best.values(), key=lambda c: -c.score)[:top_k]
    return [Candidate(chunk=c.chunk, score=c.score, rank=i) for i, c in enumerate(ordered)]


class LinearFlow(Orchestrator):
    """The v1 orchestrator: a single fixed stage sequence, executed exactly once."""

    def run(self, config, question: str, principal: Principal, ctx) -> AnswerResult:
        request_id = ctx.request_id
        variant_name = getattr(config, "name", "variant")
        config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(vars(config))

        cache = ctx.extras.get("cache")
        guardrail = ctx.extras.get("guardrail")
        retriever = ctx.extras.get("retriever")
        query_transformer = ctx.extras.get("query_transformer")
        post_retrieval_processor = ctx.extras.get("post_retrieval_processor")
        reranker = ctx.extras.get("reranker")
        governance_filter = ctx.extras.get("governance_filter")
        audit_sink = ctx.extras.get("audit_sink")

        trace = Trace(request_id=request_id, variant_name=variant_name)
        ctx.extras.setdefault("traces", {})[request_id] = trace

        def _record(stage: str, input_size: int, start: float, token_usage: int = 0, cost_estimate: float = 0.0) -> float:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            trace.stages.append(StageTrace(
                stage=stage, input_size=input_size, elapsed_ms=elapsed_ms,
                token_usage=token_usage, cost_estimate=cost_estimate,
            ))
            trace.total_token_usage += token_usage
            trace.total_cost_estimate += cost_estimate
            return elapsed_ms

        per_stage_timing: dict[str, float] = {}

        # --- cache check-first (Req 9.1, 18) ---
        # Bypassed entirely for conversational turns: the cache key is (principal,
        # config, question) only, so a repeated question in a *different*
        # conversation would otherwise return a stale answer that ignores the
        # current conversation's history.
        history = ctx.extras.get("history")
        cache_key = None
        if cache is not None and not history:
            cache_key = cache.key(principal, config_dict, question)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        # --- input guardrail ---
        start = time.perf_counter()
        if guardrail is not None:
            verdict: GuardrailVerdict = guardrail.screen_input(question)
        else:
            verdict = GuardrailVerdict(allowed=True, flagged=False, reason="", text=question)
        per_stage_timing["input_guardrail"] = _record("input_guardrail", len(question), start)

        if not verdict.allowed:
            return AnswerResult(
                variant_name=variant_name,
                answer=f"Request blocked: {verdict.reason}",
                citations=[],
                retrieved_chunks=[],
                reranked_chunks=[],
                per_stage_timing=per_stage_timing,
                governance_filtered_count=0,
                trace_id=request_id,
                no_accessible_context=False,
            )
        effective_question = verdict.text or question

        # --- query transform (Req 16) ---
        start = time.perf_counter()
        plan = query_transformer.transform(effective_question, ctx)
        per_stage_timing["query_transform"] = _record("query_transform", len(effective_question), start)

        # --- retrieval (Req 4) ---
        start = time.perf_counter()
        top_k = getattr(config, "top_k", 20)
        if len(plan.queries) <= 1:
            candidates = retriever.retrieve(plan.queries[0] if plan.queries else effective_question, top_k, ctx)
        else:
            per_query = [retriever.retrieve(q, top_k, ctx) for q in plan.queries]
            candidates = _merge_candidates(per_query, top_k) if plan.merge else per_query[0]
        per_stage_timing["retrieval"] = _record("retrieval", len(plan.queries), start)

        # --- governance filter (Req 11, safety-critical) ---
        start = time.perf_counter()
        filter_result = governance_filter.filter(candidates, principal, request_id=request_id, audit=audit_sink)
        per_stage_timing["governance"] = _record("governance", len(candidates), start)

        if not filter_result.authorized:
            return AnswerResult(
                variant_name=variant_name,
                answer=NO_CONTEXT_MESSAGE,
                citations=[],
                retrieved_chunks=[],
                reranked_chunks=[],
                per_stage_timing=per_stage_timing,
                governance_filtered_count=filter_result.filtered_count,
                trace_id=request_id,
                no_accessible_context=True,
            )

        retrieved_chunks = [c.chunk for c in filter_result.authorized]

        # --- post-retrieval (Req 17) ---
        start = time.perf_counter()
        processed_chunks = post_retrieval_processor.process(effective_question, retrieved_chunks, ctx)
        per_stage_timing["post_retrieval"] = _record("post_retrieval", len(retrieved_chunks), start)

        # --- rerank (Req 4.6, 4.7) ---
        start = time.perf_counter()
        rerank_top_k = getattr(config, "rerank_top_k", 5)
        if hasattr(reranker, "rerank_with_llm"):
            reranked_chunks = reranker.rerank_with_llm(
                effective_question, processed_chunks, rerank_top_k, ctx.generation_llm
            )
        else:
            reranked_chunks = reranker.rerank(effective_question, processed_chunks, rerank_top_k)
        per_stage_timing["rerank"] = _record("rerank", len(processed_chunks), start)

        # --- generate (Req 5) ---
        start = time.perf_counter()
        gen_output = ctx.generation_llm.generate(effective_question, reranked_chunks, history=history)
        per_stage_timing["generate"] = _record(
            "generate", len(reranked_chunks), start,
            token_usage=gen_output.token_usage, cost_estimate=gen_output.cost_estimate,
        )

        # --- output guardrail ---
        start = time.perf_counter()
        if guardrail is not None:
            out_verdict = guardrail.screen_output(gen_output.answer)
        else:
            out_verdict = GuardrailVerdict(allowed=True, flagged=False, reason="", text=gen_output.answer)
        per_stage_timing["output_guardrail"] = _record("output_guardrail", len(gen_output.answer), start)

        final_answer = out_verdict.text if out_verdict.allowed else f"Response blocked: {out_verdict.reason}"
        final_citations = gen_output.citations if out_verdict.allowed else []

        result = AnswerResult(
            variant_name=variant_name,
            answer=final_answer,
            citations=final_citations,
            retrieved_chunks=retrieved_chunks,
            reranked_chunks=reranked_chunks,
            per_stage_timing=per_stage_timing,
            governance_filtered_count=filter_result.filtered_count,
            trace_id=request_id,
            no_accessible_context=False,
        )

        # --- cache store-last (Req 9.1, 18.4: only post-governance results) ---
        if cache is not None and cache_key is not None:
            cache.put(cache_key, result)

        return result


def make_orchestrator(name: str) -> Orchestrator:
    """Construct the Orchestrator registered under ``name`` (Req 1.1, 21)."""
    if name == "linear":
        return LinearFlow()
    raise ValueError(f"Unknown orchestrator option: '{name}'")
