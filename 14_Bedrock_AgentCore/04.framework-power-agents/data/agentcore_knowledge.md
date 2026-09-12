# AgentCore Research Knowledge Base

This document is indexed by the research agent's `search_docs` RAG tool.

## Runtime

Amazon Bedrock AgentCore **Runtime** hosts your agent as a container.
You deploy with `agentcore configure` + `agentcore launch`.
Clients call `InvokeAgentRuntime` with a JSON payload (`prompt`, `actor_id`, `thread_id`).
For Identity (OAuth) to work with SIGV4, pass `runtimeUserId` so the platform mints a Workload Access Token (WAT).

This demo's research Runtime runs LangGraph inside the container. Streamlit does **not** run LangGraph locally — it only invokes the cloud Runtime.

## Memory

AgentCore **Memory** stores short-term checkpoints and longer-term records keyed by `actor_id` + `thread_id`.
Set `MEMORY_ID` at launch (example: `memorybot-w6GzC7D97L`).
The research agent uses `AgentCoreMemorySaver` + `AgentCoreMemoryStore` and `MemoryMiddleware` so multi-turn chats can recall prior turns in the same thread.

## Gateway

AgentCore **Gateway** exposes external tools behind a managed MCP HTTPS endpoint.
This project uses a Cognito M2M authorizer. Credentials live in `gateway-credentials.json`.
Demo Lambda tools on the gateway: `get_weather(location)`, `get_time(timezone)`.

## MCP (Model Context Protocol)

**MCP** is the protocol the Gateway speaks (`tools/list`, `tools/call` over JSON-RPC).
The research agent loads Gateway MCP tools via `load_gateway_mcp_tools(GATEWAY_URL, token)` and converts them into LangChain tools.
Local tools (web_search, calculator, datetime, search_docs) are **not** MCP — they run in-process.

## Identity

AgentCore **Identity** mints OAuth tokens for outbound calls (here: Gateway Cognito).
Provider name: `gateway-cognito-m2m` (Custom OAuth2 / client credentials).
Scopes: `lauki-demo-gateway/invoke`.
Flow: M2M via `@requires_access_token`. If Identity fails, the agent can fall back to `GATEWAY_TOKEN`.

## RAG / Documentation search

The `search_docs` tool retrieves chunks from this knowledge base (also shipped as `rag_data/agentcore_knowledge.md` because AgentCore’s CodeBuild zip filter excludes `docs/`) and the Lauki FAQ CSV (`lauki_qna.csv`) using keyword overlap retrieval (lightweight RAG without a vector DB dependency in the Runtime image).
Use it for questions about AgentCore concepts, Runtime/Memory/Gateway/Identity, or Lauki phone FAQs.

## Local tools summary

| Tool | Purpose |
|---|---|
| web_search | Public web (Tavily or DuckDuckGo) |
| calculator | Arithmetic |
| get_current_datetime | UTC clock |
| search_docs | RAG over this doc + FAQ |
| get_weather / get_time | Gateway MCP (Identity-auth) |
