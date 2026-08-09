"""GenerationLLM options: produces the final grounded, cited answer (Req 5).

OpenAI models (`gpt-4o-mini`, `gpt-4o`) call the OpenAI API directly; OpenRouter
models call the same OpenAI-compatible client pointed at OpenRouter's base URL and
are available only when ``OPENROUTER_API_KEY`` is present (Req 5.1, 9.2, 9.4). The
system message instructs the model to answer ONLY from the supplied context chunks,
cite the chunk ids it used, and say the not-found phrase when the context is
insufficient (Req 5.2, 5.3, 5.5). Because ``context_chunks`` is always the
orchestrator's post-governance chunk list, an unauthorized chunk is structurally
never available to cite (Req 5.6, 14.1). A missing required key or a provider-call
failure is wrapped in a descriptive error naming the module and provider message,
never a key value.

``history`` (a bounded, already sliding-window-trimmed list of prior turns) is
threaded through as real chat messages — not folded into a single text blob — so a
conversational caller gets the same multi-turn behavior a native chat API gives
ChatGPT/Claude, while a stateless single-shot caller (``history=None``) behaves
exactly as before.
"""
from __future__ import annotations

import os
import re

from rag.interfaces import Chunk, Citation, ConversationTurn, GenerationLLM, GenerationOutput

NOT_FOUND_TEXT = "answer not found in provided context"


class MissingApiKeyError(Exception):
    """Raised when a key-gated generation LLM is selected without its required key."""

    def __init__(self, env_key: str, module: str):
        self.env_key = env_key
        self.module = module
        super().__init__(f"'{module}' requires the environment key '{env_key}', which is not set.")


class GenerationProviderError(Exception):
    """Wraps a provider-call failure, naming the module and provider message only
    (never a key value) (Req 14.1)."""

    def __init__(self, module: str, provider_message: str):
        self.module = module
        self.provider_message = provider_message
        super().__init__(f"'{module}' generation call failed: {provider_message}")


def _system_message(context_chunks: list[Chunk]) -> str:
    if not context_chunks:
        context_block = "(no context chunks supplied)"
    else:
        context_block = "\n\n".join(f"[{c.id}] (source: {c.source})\n{c.text}" for c in context_chunks)
    return (
        "Answer the question using ONLY the context chunks below. Cite the chunk ids you "
        "used in square brackets, e.g. [chunk_id]. If the context is insufficient to answer, "
        f'respond exactly with: "{NOT_FOUND_TEXT}".\n\n'
        f"Context:\n{context_block}"
    )


def _build_messages(
    question: str, context_chunks: list[Chunk], history: list[ConversationTurn] | None = None
) -> list[dict]:
    """System message (grounding instructions + context) + prior turns + the new
    question, as real chat messages (Req: conversational chat memory)."""
    messages = [{"role": "system", "content": _system_message(context_chunks)}]
    for turn in history or []:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": question})
    return messages


def _extract_citations(answer: str, context_chunks: list[Chunk]) -> list[Citation]:
    """Only ever cites chunk ids present in the supplied (post-governance) context."""
    by_id = {c.id: c for c in context_chunks}
    citations: list[Citation] = []
    seen: set[str] = set()
    for cid in re.findall(r"\[([^\[\]]+)\]", answer):
        chunk = by_id.get(cid)
        if chunk is None or cid in seen:
            continue
        seen.add(cid)
        citations.append(Citation(chunk_id=chunk.id, source=chunk.source))
    return citations


def _chat_complete(client, model: str, temperature: float, messages: list[dict], module: str) -> tuple[str, int]:
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=messages,
        )
    except Exception as exc:  # provider SDK exceptions vary by provider
        raise GenerationProviderError(module, str(exc)) from exc
    answer = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    token_usage = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0
    return answer, token_usage


class OpenAIGenerationLLM(GenerationLLM):
    """OpenAI Chat Completions — requires OPENAI_API_KEY (Req 5.1, 9.2)."""

    module_name = "rag.generate.OpenAIGenerationLLM"

    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    def generate(
        self, question: str, context_chunks: list[Chunk], history: list[ConversationTurn] | None = None
    ) -> GenerationOutput:
        if not os.getenv("OPENAI_API_KEY"):
            raise MissingApiKeyError("OPENAI_API_KEY", self.module_name)
        from openai import OpenAI  # lazy import

        client = OpenAI()
        messages = _build_messages(question, context_chunks, history)
        answer, token_usage = _chat_complete(client, self.model, self.temperature, messages, self.module_name)
        citations = _extract_citations(answer, context_chunks)
        return GenerationOutput(answer=answer, citations=citations, token_usage=token_usage, cost_estimate=0.0)


class OpenRouterGenerationLLM(GenerationLLM):
    """OpenRouter via the OpenAI-compatible endpoint — requires OPENROUTER_API_KEY (Req 5.1, 9.2)."""

    module_name = "rag.generate.OpenRouterGenerationLLM"

    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    def generate(
        self, question: str, context_chunks: list[Chunk], history: list[ConversationTurn] | None = None
    ) -> GenerationOutput:
        if not os.getenv("OPENROUTER_API_KEY"):
            raise MissingApiKeyError("OPENROUTER_API_KEY", self.module_name)
        from openai import OpenAI  # lazy import

        client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
        messages = _build_messages(question, context_chunks, history)
        answer, token_usage = _chat_complete(client, self.model, self.temperature, messages, self.module_name)
        citations = _extract_citations(answer, context_chunks)
        return GenerationOutput(answer=answer, citations=citations, token_usage=token_usage, cost_estimate=0.0)


def make_llm(name: str, temperature: float = 0.0) -> GenerationLLM:
    """Construct the GenerationLLM registered under ``name`` (Req 1.1, 5.1, 9.2, 9.4)."""
    from rag import registry as R

    opt = R.get_option("generation_llm", name)
    if opt is None:
        raise ValueError(f"Unknown generation_llm option: '{name}'")
    provider = opt.meta.get("provider")
    model = opt.meta.get("model", name)
    if provider == "openrouter":
        return OpenRouterGenerationLLM(model, temperature)
    return OpenAIGenerationLLM(model, temperature)
