"""Observability: builds Trace/StageTrace and emits structured logs (Req 19).

The ``TraceRecorder`` accumulates one ``StageTrace`` per pipeline stage (ordered
stages, input sizes, per-stage timing, token usage, cost estimate) into a ``Trace``
(Req 19.1). Local modules always record zero token usage/cost (Req 19.4, 22.1) —
callers simply never pass a nonzero value for a local stage. Structured logs go to
console and a local file (Req 19.5). ``Trace`` never carries removed-chunk content or
Env_Key values by construction (Req 19.6) — this module only ever serializes the
``Trace``/``StageTrace`` dataclasses, which have no such fields.
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import asdict

from rag.interfaces import StageTrace, Trace

# Illustrative per-1K-token cost estimates for known API-based generation models
# (Req 19.1). Unlisted/local models always cost 0.0 (Req 19.4, 22.1).
_COST_PER_1K_TOKENS: dict[str, float] = {
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.0025,
    "text-embedding-3-small": 0.00002,
    "text-embedding-3-large": 0.00013,
}


def estimate_cost(model: str, token_usage: int) -> float:
    """A rough per-1K-token cost estimate; 0.0 for any unlisted (typically local) model."""
    rate = _COST_PER_1K_TOKENS.get(model)
    if rate is None:
        return 0.0
    return round((token_usage / 1000.0) * rate, 6)


class TraceRecorder:
    """Accumulates StageTraces for one request into a Trace (Req 19.1-19.4)."""

    def __init__(self, request_id: str, variant_name: str):
        self.trace = Trace(request_id=request_id, variant_name=variant_name)

    def record(self, stage_trace: StageTrace) -> None:
        self.trace.stages.append(stage_trace)
        self.trace.total_token_usage += stage_trace.token_usage
        self.trace.total_cost_estimate += stage_trace.cost_estimate

    def finalize(self, governance_filtered_count: int = 0) -> Trace:
        self.trace.governance_filtered_count = governance_filtered_count
        return self.trace


@contextmanager
def timed_stage(recorder: TraceRecorder, stage: str, input_size: int = 0):
    """Times one stage and records it on ``recorder`` on exit.

    Yields a mutable dict the caller may set ``token_usage``/``cost_estimate`` on
    (nonzero only for API-based stages — Req 19.4).
    """
    info = {"token_usage": 0, "cost_estimate": 0.0}
    start = time.perf_counter()
    try:
        yield info
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        recorder.record(
            StageTrace(
                stage=stage,
                input_size=input_size,
                elapsed_ms=elapsed_ms,
                token_usage=int(info.get("token_usage", 0) or 0),
                cost_estimate=float(info.get("cost_estimate", 0.0) or 0.0),
            )
        )


_LOGGER_NAME = "rag_studio"


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    log_path = os.getenv("RAG_STUDIO_LOG_FILE", "./rag_studio.log")
    try:
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(file_handler)
    except OSError:
        pass  # unwritable path (e.g. read-only test sandbox) — console logging still works
    return logger


def log_trace(trace: Trace) -> None:
    """Emit a structured (JSON) log line for one Trace to console + local file (Req 19.5)."""
    logger = _configure_logger()
    payload = {
        "request_id": trace.request_id,
        "variant_name": trace.variant_name,
        "stages": [asdict(s) for s in trace.stages],
        "total_token_usage": trace.total_token_usage,
        "total_cost_estimate": trace.total_cost_estimate,
        "governance_filtered_count": trace.governance_filtered_count,
    }
    logger.info(json.dumps(payload, default=str))
