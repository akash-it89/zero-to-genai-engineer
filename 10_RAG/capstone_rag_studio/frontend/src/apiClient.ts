// apiClient: the SPA's only path to the backend. Attaches the current
// Acting_Principal to every request — the SPA never calls providers directly
// (Req 10.4, 10.5, 11.7).

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface Principal {
  id: string;
  roles: string[];
}

export class ApiError extends Error {
  status: number;
  code: string;
  module: string | null;
  variant: string | null;

  constructor(status: number, code: string, message: string, module: string | null, variant: string | null) {
    super(message);
    this.status = status;
    this.code = code;
    this.module = module;
    this.variant = variant;
  }
}

function principalHeaders(principal: Principal): Record<string, string> {
  const headers: Record<string, string> = { "X-Principal-Id": principal.id };
  if (principal.roles.length > 0) {
    headers["X-Principal-Roles"] = principal.roles.join(",");
  }
  return headers;
}

async function request<T>(
  principal: Principal,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { ...principalHeaders(principal) };
  let requestBody: BodyInit | undefined;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  const resp = await fetch(`${BASE_URL}${path}`, { method, headers, body: requestBody });
  const data = await resp.json().catch(() => ({}));

  if (!resp.ok) {
    const err = data?.error ?? {};
    throw new ApiError(
      resp.status,
      err.code ?? "UNKNOWN_ERROR",
      err.message ?? `Request to ${path} failed with status ${resp.status}`,
      err.module ?? null,
      err.variant ?? null,
    );
  }
  return data as T;
}

export interface OptionEntry {
  key: string;
  label: string;
  stage_interface: string;
  available: boolean;
  reserved: boolean;
  reserved_target: string | null;
  requires_key: string | null;
  is_local: boolean;
}

export type OptionsCatalog = Record<string, Record<string, OptionEntry>>;

export interface PipelineConfig {
  name: string;
  chunk_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  embedding: string;
  vector_store: string;
  query_transform: string;
  retrieval: string;
  top_k: number;
  alpha: number;
  rrf_k: number;
  post_retrieval: string;
  reranker: string;
  rerank_top_k: number;
  llm: string;
  temperature: number;
  orchestrator: string;
  caching: string;
  guardrails: string;
}

export interface Citation {
  chunk_id: string;
  source: string;
}

export interface AnswerResult {
  variant_name: string;
  answer: string;
  citations: Citation[];
  retrieved_chunks: unknown[];
  reranked_chunks: unknown[];
  per_stage_timing: Record<string, number>;
  governance_filtered_count: number;
  trace_id: string;
  no_accessible_context: boolean;
}

export interface ChatResponse {
  results: Record<string, AnswerResult>;
  errors: Record<string, string>;
}

export interface StageTrace {
  stage: string;
  input_size: number;
  elapsed_ms: number;
  token_usage: number;
  cost_estimate: number;
}

export interface Trace {
  request_id: string;
  variant_name: string;
  stages: StageTrace[];
  total_token_usage: number;
  total_cost_estimate: number;
  governance_filtered_count: number;
}

export interface MetricScoresResponse {
  scores: Record<string, number>;
  passed: Record<string, boolean>;
  reasons: Record<string, string>;
  excluded_reference_dependent: string[];
}

export interface RetrievalMetrics {
  overall: Record<string, number>;
  by_query_type: Record<string, Record<string, number>>;
}

export interface RetrievalEvaluationResponse {
  results: Record<string, RetrievalMetrics>;
  errors: Record<string, string>;
}

export interface RetrievalGoldenItem {
  question: string;
  expected_sources: string[];
  query_type?: string;
}

export interface AccessPolicyResponse {
  access_level: "PUBLIC" | "RESTRICTED" | "PRIVATE";
  owner: string;
  acl: string[];
}

export interface ConversationSummary {
  id: string;
  variant_name: string;
  created_at: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  trace_id: string | null;
  created_at: string;
}

export const api = {
  health: () => request<{ status: string; warnings: string[] }>({ id: "", roles: [] }, "GET", "/health"),

  getOptions: (principal: Principal) => request<OptionsCatalog>(principal, "GET", "/options"),

  listVariants: (principal: Principal) => request<Record<string, PipelineConfig>>(principal, "GET", "/variants"),

  saveVariant: (principal: Principal, config: Partial<PipelineConfig> & { name: string }) =>
    request<{ status: string; name: string }>(principal, "POST", "/variants", config),

  deleteVariant: (principal: Principal, name: string) =>
    request<{ status: string; name: string }>(principal, "DELETE", `/variants/${encodeURIComponent(name)}`),

  ingest: (principal: Principal, files: File[], accessLevel: string, acl: string) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    form.append("access_level", accessLevel);
    form.append("acl", acl);
    return request<{ ingested: string[] }>(principal, "POST", "/ingest", form);
  },

  buildIndex: (principal: Principal, variantName: string) =>
    request<{ status: string; variant_name: string; chunk_count: number }>(principal, "POST", "/index", {
      variant_name: variantName,
    }),

  chat: (principal: Principal, question: string, variantNames?: string[]) =>
    request<ChatResponse>(principal, "POST", "/chat", { question, variant_names: variantNames ?? null }),

  getTrace: (principal: Principal, requestId: string) =>
    request<Trace>(principal, "GET", `/trace/${encodeURIComponent(requestId)}`),

  evaluateLive: (principal: Principal, samples: unknown[], framework: string, metrics: string[]) =>
    request<MetricScoresResponse>(principal, "POST", "/evaluate/live", { samples, framework, metrics }),

  evaluateGolden: (principal: Principal, samples: unknown[], framework: string, metrics: string[]) =>
    request<MetricScoresResponse>(principal, "POST", "/evaluate/golden", { samples, framework, metrics }),

  evaluateRetrieval: (principal: Principal, goldenSet: RetrievalGoldenItem[], variantNames: string[]) =>
    request<RetrievalEvaluationResponse>(principal, "POST", "/evaluate/retrieval", {
      golden_set: goldenSet,
      variant_names: variantNames.length > 0 ? variantNames : null,
    }),

  getPolicy: (principal: Principal, docId: string) =>
    request<AccessPolicyResponse>(principal, "GET", `/governance/policy/${encodeURIComponent(docId)}`),

  setPolicy: (principal: Principal, docId: string, policy: AccessPolicyResponse) =>
    request<{ status: string; doc_id: string }>(
      principal, "POST", `/governance/policy/${encodeURIComponent(docId)}`, policy,
    ),

  listConversations: (principal: Principal) =>
    request<ConversationSummary[]>(principal, "GET", "/conversations"),

  startConversation: (principal: Principal, variantName: string) =>
    request<{ conversation_id: string; variant_name: string }>(principal, "POST", "/conversations", {
      variant_name: variantName,
    }),

  getConversationMessages: (principal: Principal, conversationId: string) =>
    request<{ messages: ConversationMessage[] }>(
      principal, "GET", `/conversations/${encodeURIComponent(conversationId)}/messages`,
    ),

  postConversationMessage: (principal: Principal, conversationId: string, content: string) =>
    request<AnswerResult>(
      principal, "POST", `/conversations/${encodeURIComponent(conversationId)}/messages`, { content },
    ),
};
