"""
Evaluation pipeline for the Production RAG Chatbot + Memory app.

Given the chunks already indexed by a HybridIndex, this module:

  1. Generates a synthetic test set -- N questions per chunk, one LLM call per
     chunk. The chunk that produced a question IS that question's ground truth --
     no manual labeling needed, because the question was written to be answerable
     only from that specific passage.

  2. Evaluates retrieval quality (Recall@1/3/10, NDCG@10, MCC@1/3/10) by running
     each question through the REAL retrieval pipeline this app actually uses
     (dense + BM25, RRF fusion, cross-encoder rerank) and checking where the
     source chunk lands in the ranked results. Hand-rolled, not a library call --
     the math is simple enough that a library would only hide it, and every other
     retrieval-internals feature in this app (RRF, BM25 scoring) is transparent
     for the same reason.

  3. Evaluates generation quality with RAGAS and DeepEval -- real libraries, not
     hand-rolled, because faithfulness/relevancy scoring done wrong is worse than
     not having it. Each question is answered using the same grounded-answer
     prompt Notebook 13's ProductionRAGChatbot uses, in isolation from the live
     agent (no chat history, no long-term memory side effects -- evaluation
     questions must never leak into a real conversation thread).

Deliberately NOT wired to run automatically after every "Build knowledge base"
click. A modest 15-chunk document at 2 questions/chunk is 30 questions; each one
needs a generation call plus four RAGAS judge calls plus four DeepEval judge
calls -- 200+ LLM calls per run. That's real time and real money every time
someone uploads a document. Evaluation here is a deliberate, on-demand action
(see the Evaluation tab in app.py), not a hidden tax on the fast iteration loop.

Compatibility note: ragas 0.4.3 unconditionally imports
`langchain_community.chat_models.vertexai.ChatVertexAI` for a static
`isinstance()` check in a support-matrix list -- the class is never instantiated.
That submodule no longer exists in current langchain-community releases (Vertex AI
moved to its own package), so the import crashes before ragas is even usable. The
shim below registers a dummy module satisfying that import. This is safe because
this app never uses Vertex AI (OpenAI only); if you upgrade ragas and this import
succeeds without the shim, delete this block.
"""

import concurrent.futures
import sys
import time
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field
from sklearn.metrics import matthews_corrcoef

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

# rag_pipeline.py lives in the sibling production_rag_chatbot/ project, same as
# rag_agent_pipeline.py's import of it -- add it independently rather than relying
# on import order (this module should work whether or not rag_agent_pipeline was
# imported first).
_sibling_path = str(Path(__file__).parent.parent / "production_rag_chatbot")
if _sibling_path not in sys.path:
    sys.path.insert(0, _sibling_path)

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _vertex_stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class _StubChatVertexAI:  # pragma: no cover - compatibility shim only, never instantiated
        pass

    _vertex_stub.ChatVertexAI = _StubChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _vertex_stub

from ragas.llms import llm_factory  # noqa: E402
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings  # noqa: E402
from ragas.metrics.collections import (  # noqa: E402
    Faithfulness as RagasFaithfulness,
    AnswerRelevancy as RagasAnswerRelevancy,
    ContextPrecisionWithReference as RagasContextPrecision,
    ContextRecall as RagasContextRecall,
)

from deepeval.test_case import LLMTestCase  # noqa: E402
from deepeval.metrics import (  # noqa: E402
    FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric, ContextualRecallMetric,
)

from rag_pipeline import ANSWER_PROMPT, format_sources  # noqa: E402

EVAL_MODEL = "gpt-4o-mini"
EVAL_EMBEDDING_MODEL = "text-embedding-3-small"


CALL_TIMEOUT_S = 60  # hard ceiling per external call (LLM generation, judge scoring,
# embedding). Verified live against this environment: some judge calls that
# complete in ~2s in isolation occasionally stall far longer under sustained load
# (network/rate-limit variance, not a code bug) -- without a hard timeout, one
# stalled call blocks the entire evaluation run, and the Streamlit UI thread
# driving it, indefinitely.


def _call_with_timeout(fn, timeout=CALL_TIMEOUT_S):
    """Run fn() with a wall-clock ceiling. Python threads can't be forcibly killed,
    so a timed-out call keeps running in the background after we stop waiting on
    it -- but the caller is freed immediately, which is what actually matters for
    keeping the pipeline (and the UI) responsive. shutdown(wait=False) is
    deliberate: waiting here would defeat the entire point of the timeout."""
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(fn)
        return future.result(timeout=timeout)
    finally:
        pool.shutdown(wait=False)


def _retry_once(fn, timeout=CALL_TIMEOUT_S):
    """LLM-judge calls occasionally fail transiently (network stalls, rate limits,
    a rare runaway structured-output generation). One retry, each attempt bounded
    by _call_with_timeout, catches the common transient case without a single
    flaky call aborting -- or hanging -- an entire evaluation run. Returns
    (value, error_message) -- error_message is None on success."""
    try:
        return _call_with_timeout(fn, timeout), None
    except Exception:
        try:
            return _call_with_timeout(fn, timeout), None
        except Exception as exc2:
            return None, str(exc2)


# ---- 1. Test-set generation -------------------------------------------------

QUESTION_GEN_PROMPT = """You are building an evaluation test set for a document retrieval system.

Given ONLY the passage below, write {n} distinct question(s) that:
- Can be answered using ONLY the information in this passage
- Are specific enough that a passage on a DIFFERENT topic would NOT answer them
- Do not quote the passage verbatim -- use natural question phrasing
- Vary in style if the passage supports it (factual, "how", "why", comparison)

Passage:
\"\"\"
{passage}
\"\"\""""


class _GeneratedQuestions(BaseModel):
    questions: list[str] = Field(description="The generated evaluation questions, in order.")


def _even_sample(items, max_n):
    """Evenly-spaced sample across the whole list, not just the head -- same
    sampling philosophy as summarize_document in rag_agent_pipeline.py, so the
    test set covers the whole document instead of just its first N chunks."""
    if len(items) <= max_n:
        return list(items)
    step = max(1, len(items) // max_n)
    return items[::step][:max_n]


def generate_test_set(chunks, questions_per_chunk=2, max_chunks=15, model=EVAL_MODEL):
    """One question-generation call per sampled chunk. Returns a list of
    {question, source_chunk_id, source_chunk_text, source, page} -- the chunk IS
    the ground truth, by construction."""
    sample = _even_sample(chunks, max_chunks)
    llm = ChatOpenAI(model=model, temperature=0.7).with_structured_output(_GeneratedQuestions)

    test_set = []
    for chunk in sample:
        result, err = _retry_once(
            lambda c=chunk: llm.invoke(QUESTION_GEN_PROMPT.format(n=questions_per_chunk, passage=c["text"]))
        )
        if result is None:
            continue  # skip this chunk's questions rather than aborting the whole run
        for q in result.questions[:questions_per_chunk]:
            if q.strip():
                test_set.append({
                    "question": q.strip(),
                    "source_chunk_id": chunk["id"],
                    "source_chunk_text": chunk["text"],
                    "source": chunk["source"],
                    "page": chunk["page"],
                })
    return test_set


# ---- 2. Retrieval evaluation -------------------------------------------------

def _generate_answer(question, reranked_top, model=EVAL_MODEL):
    llm = ChatOpenAI(model=model, temperature=0)
    prompt = ANSWER_PROMPT.format(
        sources=format_sources(reranked_top), history="(none -- standalone evaluation question)",
        question=question,
    )
    return llm.invoke(prompt).content


def _run_retrieval_and_generation(test_set, index, reranker, top_k, top_n, model, on_progress=None):
    """One retrieval pass per question, feeding both retrieval metrics and
    generation metrics (the answer + contexts actually produced) -- avoids
    retrieving twice per question.

    Records TWO ranks per question, not one: `fused_rank` is where the source
    chunk lands right after dense+BM25 RRF fusion, BEFORE the cross-encoder
    touches anything -- this isolates "how good is retrieval" on its own.
    `rerank_rank` is where it lands AFTER the cross-encoder reorders that exact
    same candidate pool -- comparing the two in isolation is what actually
    answers "how much is reranking helping," which raw Recall@K alone can't (it
    only ever shows you the combined result of both stages at once).
    """
    per_question_retrieval = []
    items_with_answers = []
    total = len(test_set)

    def _retrieve(question):
        debug = index.search_debug(question, k=top_k)
        reranked = reranker.rerank_all(question, debug["fused_chunks"])
        return debug["fused_chunks"], reranked

    for i, item in enumerate(test_set):
        if on_progress:
            on_progress(f"Retrieving + generating ({i + 1}/{total})...")

        # Retrieval makes a real embedding API call (query embedding) -- bound it
        # the same way as any other external call, so one stalled request can't
        # freeze the whole evaluation run.
        result, retrieval_err = _retry_once(lambda q=item["question"]: _retrieve(q))
        if result is None:
            per_question_retrieval.append({
                "question": item["question"], "source": item["source"], "page": item["page"],
                "source_chunk_id": item["source_chunk_id"],
                "fused_rank": None, "rerank_rank": None, "pool_size": 0,
                "retrieval_error": retrieval_err,
            })
            items_with_answers.append({
                "question": item["question"], "answer": "",
                "contexts": ["(retrieval failed)"], "reference": item["source_chunk_text"],
                "generation_error": f"retrieval failed: {retrieval_err}",
            })
            continue

        fused_chunks, reranked_all = result

        def _find_rank(ordered_chunks, chunk_id=item["source_chunk_id"]):
            return next(
                (pos + 1 for pos, c in enumerate(ordered_chunks) if c.get("id") == chunk_id), None,
            )

        fused_rank = _find_rank(fused_chunks)
        rerank_rank = _find_rank([c for c, _s in reranked_all])
        per_question_retrieval.append({
            "question": item["question"], "source": item["source"], "page": item["page"],
            "source_chunk_id": item["source_chunk_id"],
            "fused_rank": fused_rank, "rerank_rank": rerank_rank, "pool_size": len(reranked_all),
        })

        reranked_top = reranked_all[:top_n]
        answer, gen_err = _retry_once(lambda q=item["question"], r=reranked_top: _generate_answer(q, r, model))
        items_with_answers.append({
            "question": item["question"],
            "answer": answer if answer is not None else "",
            "contexts": [c["text"] for c, _s in reranked_top] or ["(no context retrieved)"],
            "reference": item["source_chunk_text"],
            "generation_error": gen_err,
        })

    return per_question_retrieval, items_with_answers


def _stage_metrics(per_question, rank_key):
    """Recall@K, NDCG@K, and MRR are standard for this single-relevant-item
    setup. Computed generically over whichever rank was recorded for this stage
    (`fused_rank` for retrieval alone, `rerank_rank` for after reranking), so the
    exact same math answers two different questions depending on which key is
    passed in.

    MCC@K is included because it was explicitly requested, with one caveat worth
    keeping in mind when reading it: MCC is a binary-classification metric, not a
    ranking metric. It's computed here by treating every (question, pool item)
    pair as a binary prediction -- "is this chunk in the top-K?" vs. "is this
    actually the source chunk?" -- flattened into one confusion matrix via
    sklearn.matthews_corrcoef. With one true positive per question against a
    pool of `top_k` candidates, class imbalance is severe; treat MCC as a
    secondary signal alongside Recall@K and NDCG@K, not a standalone verdict.
    """
    def recall_at(k):
        hits = [1 if (r[rank_key] is not None and r[rank_key] <= k) else 0 for r in per_question]
        return float(np.mean(hits)) if hits else 0.0

    def ndcg_at(k):
        vals = [
            1.0 / np.log2(r[rank_key] + 1) if (r[rank_key] is not None and r[rank_key] <= k) else 0.0
            for r in per_question
        ]
        return float(np.mean(vals)) if vals else 0.0

    def mrr():
        vals = [1.0 / r[rank_key] if r[rank_key] is not None else 0.0 for r in per_question]
        return float(np.mean(vals)) if vals else 0.0

    def mcc_at(k):
        y_true, y_pred = [], []
        for r in per_question:
            for pos in range(1, r["pool_size"] + 1):
                y_true.append(1 if r[rank_key] == pos else 0)
                y_pred.append(1 if pos <= k else 0)
            if r[rank_key] is None:
                # Source chunk missing from the pool entirely -- a false negative
                # that never had a chance to be "predicted," but still belongs in
                # the confusion matrix as a miss.
                y_true.append(1)
                y_pred.append(0)
        if len(set(y_true)) < 2 or len(set(y_pred)) < 2:
            return None  # undefined when one class is entirely absent
        return float(matthews_corrcoef(y_true, y_pred))

    return {
        "recall_at_1": recall_at(1), "recall_at_3": recall_at(3), "recall_at_10": recall_at(10),
        "ndcg_at_10": ndcg_at(10), "mrr": mrr(),
        "mcc_at_1": mcc_at(1), "mcc_at_3": mcc_at(3), "mcc_at_10": mcc_at(10),
    }


def _aggregate_retrieval_metrics(per_question):
    """Two full metric blocks over the SAME candidate pool per question (fusion
    only reorders top_k candidates; reranking reorders that identical set again
    -- pool size never changes between stages) -- so any difference between them
    is attributable to the cross-encoder, not to a different candidate set.
    `reranking_lift` is that difference, computed directly rather than left for
    a reader to subtract by hand.
    """
    retrieval_only = _stage_metrics(per_question, "fused_rank")
    after_rerank = _stage_metrics(per_question, "rerank_rank")
    lift = {
        k: round(after_rerank[k] - retrieval_only[k], 4)
        for k in after_rerank
        if after_rerank[k] is not None and retrieval_only[k] is not None
    }
    return {
        "n_questions": len(per_question),
        "retrieval_only": retrieval_only,
        "after_rerank": after_rerank,
        "reranking_lift": lift,
        "per_question": per_question,
    }


# ---- 3a. Generation evaluation -- RAGAS -------------------------------------

def evaluate_ragas(items_with_answers, model=EVAL_MODEL, embedding_model=EVAL_EMBEDDING_MODEL, on_progress=None):
    """Faithfulness and AnswerRelevancy need no ground truth. ContextPrecision and
    ContextRecall do -- the source chunk's own text (the passage the question was
    generated from) serves as the reference, which is exactly the "ideal answer
    content" these metrics expect.

    Requires an AsyncOpenAI client, not a sync one -- ragas's instructor-based LLM
    wrapper calls .agenerate() internally even from the synchronous .score()/
    .batch_score() entry points; a sync OpenAI client raises
    "Cannot use agenerate() with a synchronous client" (verified directly against
    ragas 0.4.3 before writing this).
    """
    client = AsyncOpenAI()
    llm = llm_factory(model=model, provider="openai", client=client)
    embeddings = RagasOpenAIEmbeddings(client=client, model=embedding_model)

    faithfulness = RagasFaithfulness(llm=llm)
    answer_relevancy = RagasAnswerRelevancy(llm=llm, embeddings=embeddings)
    context_precision = RagasContextPrecision(llm=llm)
    context_recall = RagasContextRecall(llm=llm)

    def _score_metric(name, metric, build_kwargs):
        if on_progress:
            on_progress(f"RAGAS: scoring {name}...")
        inputs = [build_kwargs(it) for it in items_with_answers]
        # The whole batch is one call -- give it more room than a single-item
        # timeout (concurrent, but still bounded), so a stalled batch degrades to
        # the per-item fallback instead of hanging the run indefinitely.
        batch_timeout = max(CALL_TIMEOUT_S, 15 * len(inputs))
        batch_result, _batch_err = _retry_once(lambda: metric.batch_score(inputs), timeout=batch_timeout)
        if batch_result is not None:
            return [r.value for r in batch_result]

        # Batch failed or timed out entirely -- fall back to scoring one at a
        # time so a single bad/slow sample doesn't wipe out the whole metric.
        values = []
        for kw in inputs:
            val, _err = _retry_once(lambda k=kw: metric.score(**k).value)
            values.append(val)
        return values

    faith_vals = _score_metric(
        "faithfulness", faithfulness,
        lambda it: {"user_input": it["question"], "response": it["answer"], "retrieved_contexts": it["contexts"]},
    )
    ar_vals = _score_metric(
        "answer relevancy", answer_relevancy,
        lambda it: {"user_input": it["question"], "response": it["answer"]},
    )
    cp_vals = _score_metric(
        "context precision", context_precision,
        lambda it: {"user_input": it["question"], "reference": it["reference"], "retrieved_contexts": it["contexts"]},
    )
    cr_vals = _score_metric(
        "context recall", context_recall,
        lambda it: {"user_input": it["question"], "retrieved_contexts": it["contexts"], "reference": it["reference"]},
    )

    per_question = [
        {
            "question": it["question"], "faithfulness": faith_vals[i], "answer_relevancy": ar_vals[i],
            "context_precision": cp_vals[i], "context_recall": cr_vals[i],
        }
        for i, it in enumerate(items_with_answers)
    ]

    def _avg(vals):
        clean = [v for v in vals if v is not None]
        return float(np.mean(clean)) if clean else None

    return {
        "faithfulness": _avg(faith_vals), "answer_relevancy": _avg(ar_vals),
        "context_precision": _avg(cp_vals), "context_recall": _avg(cr_vals),
        "n_scored": {
            "faithfulness": sum(1 for v in faith_vals if v is not None),
            "answer_relevancy": sum(1 for v in ar_vals if v is not None),
            "context_precision": sum(1 for v in cp_vals if v is not None),
            "context_recall": sum(1 for v in cr_vals if v is not None),
        },
        "n_total": len(items_with_answers),
        "per_question": per_question,
    }


# ---- 3b. Generation evaluation -- DeepEval ----------------------------------

def evaluate_deepeval(items_with_answers, model=EVAL_MODEL, on_progress=None):
    """async_mode=True (DeepEval's default) is required here, not a stylistic
    choice: async_mode=False on FaithfulnessMetric hung for 88.5s and then failed
    on every one of three separate live attempts against this deepeval version
    (4.0.7) before this was diagnosed -- a real bug in that code path, not
    network flakiness. async_mode=True completed the same call in ~2 seconds
    across all four metrics. Do not "simplify" this to async_mode=False.

    Each (question, metric) pair is scored and isolated independently -- a single
    failure only blanks that one cell instead of losing the whole run, and the
    result reports exactly how many of N questions each metric actually scored.
    """
    faithfulness_m = FaithfulnessMetric(model=model, async_mode=True, include_reason=False)
    answer_rel_m = AnswerRelevancyMetric(model=model, async_mode=True, include_reason=False)
    ctx_prec_m = ContextualPrecisionMetric(model=model, async_mode=True, include_reason=False)
    ctx_rec_m = ContextualRecallMetric(model=model, async_mode=True, include_reason=False)
    metrics = [
        ("faithfulness", faithfulness_m), ("answer_relevancy", answer_rel_m),
        ("contextual_precision", ctx_prec_m), ("contextual_recall", ctx_rec_m),
    ]

    per_question = []
    totals = {name: [] for name, _ in metrics}
    total_items = len(items_with_answers)

    for i, it in enumerate(items_with_answers):
        if on_progress:
            on_progress(f"DeepEval: scoring question {i + 1}/{total_items}...")
        test_case = LLMTestCase(
            input=it["question"], actual_output=it["answer"],
            retrieval_context=it["contexts"], expected_output=it["reference"], context=[it["reference"]],
        )
        row = {"question": it["question"]}
        for name, metric in metrics:
            score, _err = _retry_once(lambda m=metric, t=test_case: (m.measure(t), m.score)[1])
            row[name] = score
            if score is not None:
                totals[name].append(score)
        per_question.append(row)

    def _avg(name):
        vals = totals[name]
        return float(np.mean(vals)) if vals else None

    return {
        "faithfulness": _avg("faithfulness"), "answer_relevancy": _avg("answer_relevancy"),
        "contextual_precision": _avg("contextual_precision"), "contextual_recall": _avg("contextual_recall"),
        "n_scored": {name: len(totals[name]) for name, _ in metrics},
        "n_total": total_items,
        "per_question": per_question,
    }


# ---- Orchestrator -------------------------------------------------------------

def run_evaluation(index, reranker, chunks, top_k, top_n, min_rerank_score,
                    chunking_strategy, questions_per_chunk=2, max_chunks=15,
                    run_ragas=True, run_deepeval=True, model=EVAL_MODEL, on_progress=None):
    """Full evaluation run against the currently-built knowledge base. Returns a
    single result dict meant to be saved as-is (see app.py's Evaluation tab) so
    runs across different configurations (chunking strategy, top_k, ...) can be
    compared side by side later."""
    def _p(msg):
        if on_progress:
            on_progress(msg)

    t0 = time.time()
    _p(f"Generating test set ({questions_per_chunk} question(s) x up to {max_chunks} chunk(s))...")
    test_set = generate_test_set(chunks, questions_per_chunk, max_chunks, model)
    if not test_set:
        raise RuntimeError(
            "No test questions could be generated. This usually means every "
            "question-generation call failed (e.g. no OpenAI connectivity) -- "
            "check the app logs for the underlying error."
        )

    _p(f"Running retrieval + generation for {len(test_set)} question(s)...")
    per_question_retrieval, items_with_answers = _run_retrieval_and_generation(
        test_set, index, reranker, top_k, top_n, model, on_progress=_p,
    )
    retrieval_metrics = _aggregate_retrieval_metrics(per_question_retrieval)

    ragas_metrics = None
    if run_ragas:
        try:
            ragas_metrics = evaluate_ragas(items_with_answers, model=model, on_progress=_p)
        except Exception as exc:
            ragas_metrics = {"error": str(exc)}

    deepeval_metrics = None
    if run_deepeval:
        try:
            deepeval_metrics = evaluate_deepeval(items_with_answers, model=model, on_progress=_p)
        except Exception as exc:
            deepeval_metrics = {"error": str(exc)}

    return {
        "config": {
            "chunking_strategy": chunking_strategy, "top_k": top_k, "top_n": top_n,
            "min_rerank_score": min_rerank_score, "questions_per_chunk": questions_per_chunk,
            "max_chunks": max_chunks, "model": model,
        },
        "test_set_size": len(test_set),
        "elapsed_s": round(time.time() - t0, 1),
        "retrieval": retrieval_metrics,
        "ragas": ragas_metrics,
        "deepeval": deepeval_metrics,
    }


# ---- Run persistence -- compare strategies across runs -----------------------
# Same SqliteStore that backs long-term memory and conversation threads
# (rag_agent_pipeline.py's remember_fact/record_thread/list_threads) -- just a new
# namespace, so evaluation runs survive rebuilds and restarts exactly like everything
# else in this app, and different configurations (fixed vs semantic chunking,
# different top_k) can be compared side by side later, not just eyeballed once.

def _default_label(config: dict) -> str:
    strategy = "Semantic" if config.get("chunking_strategy") == "semantic" else "Fixed-size"
    return f"{strategy} · top_k={config.get('top_k')} · top_n={config.get('top_n')}"


def save_eval_run(store, user_id: str, result: dict, label: str | None = None) -> str:
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    record = {
        **result,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label or _default_label(result["config"]),
    }
    store.put(("eval_runs", user_id), run_id, record)
    return run_id


def list_eval_runs(store, user_id: str) -> list:
    """Most recent first."""
    items = store.search(("eval_runs", user_id))
    return sorted(items, key=lambda item: item.value["created_at"], reverse=True)


def delete_eval_run(store, user_id: str, run_id: str) -> None:
    store.delete(("eval_runs", user_id), run_id)
