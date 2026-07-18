# Session 07 — LangChain Fundamentals
### M03 — Prompt Engineering Part 3

> **What was MISSING from S06:** DSPy gave us programmatic prompt optimisation — but each notebook was calling one provider at a time with custom code. LangChain provides a unified interface for calling any LLM, managing conversation history, and composing chains — all with the same API.

---

## What This Session Covers

| Concept | What You Learn |
|---------|---------------|
| Unified LLM interface | Call OpenAI, Claude, Gemini, and Ollama with identical code |
| `ChatPromptTemplate` | Reusable prompt templates with variables |
| `MessagesPlaceholder` | Inject conversation history into prompts |
| `InMemoryChatMessageHistory` | Maintain multi-turn context |
| Streaming | `.stream()` for token-by-token output |
| LCEL chains | Compose steps with the `|` pipe operator |

---

## Notebook

| File | What It Covers | Time |
|------|---------------|------|
| `langchain_claude_openai_gemini_ollama_stream.ipynb` | Full LangChain walkthrough — 4 providers, templates, history, streaming, LCEL | 60 min |

---

## Providers Used

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | `gpt-4o-mini` | Cloud API |
| Anthropic | `claude-haiku-4-5` | Cloud API |
| Google | `gemini-2.5-flash-lite` | Cloud API (free tier) |
| Ollama | `llama3.2`, `qwen2.5` | Local, free |

---

## Prerequisites

- **S06** — DSPy prompt engineering (understand typed prompts and optimisation)
- **S05** — Running LLMs locally and via APIs (Ollama setup)
- API keys for at least one cloud provider (Gemini free tier is fine)

---

## Setup

```bash
pip install langchain langchain-openai langchain-anthropic langchain-google-genai langchain-community
```

For local Ollama models, ensure Ollama is running:
```bash
ollama serve
ollama pull llama3.2
```

---

*Part of the GenAI-2026 curriculum — zero-to-genai-engineer track*
