// The Stage Rail — the orchestrator's own fixed, 8-stage pipeline order
// (rag/orchestrator.py's CANONICAL_STAGE_ORDER) rendered as a compact metrics
// table, the pattern AWS console tools use for per-resource timing/throughput.
// Each row's ProgressBar encodes that stage's real elapsed_ms relative to the
// slowest *local* stage (the `generate` stage is an API call and would
// otherwise dwarf every local stage into visual noise).
import ProgressBar from "@cloudscape-design/components/progress-bar";
import Table from "@cloudscape-design/components/table";
import type { StageTrace } from "./apiClient";

export const CANONICAL_STAGE_ORDER = [
  "input_guardrail",
  "query_transform",
  "retrieval",
  "governance",
  "post_retrieval",
  "rerank",
  "generate",
  "output_guardrail",
];

export function StageRail({
  timing,
  stages,
  testId,
}: {
  /** Either a flat stage -> ms map (per_stage_timing) ... */
  timing?: Record<string, number>;
  /** ... or full StageTrace records (from GET /trace/{id}), which also carry token usage. */
  stages?: StageTrace[];
  testId?: string;
}) {
  const byStage: Record<string, { ms: number; tokens: number }> = {};
  if (stages) {
    for (const s of stages) byStage[s.stage] = { ms: s.elapsed_ms, tokens: s.token_usage };
  } else if (timing) {
    for (const [stage, ms] of Object.entries(timing)) byStage[stage] = { ms, tokens: 0 };
  }

  const localMs = Object.entries(byStage)
    .filter(([stage]) => stage !== "generate")
    .map(([, s]) => s.ms);
  const maxLocalMs = Math.max(1, ...localMs);

  const rows = CANONICAL_STAGE_ORDER.map((stage) => {
    const entry = byStage[stage] ?? { ms: 0, tokens: 0 };
    const pct = stage === "generate" ? 100 : Math.min(100, (entry.ms / maxLocalMs) * 100);
    return { stage, ms: entry.ms, tokens: entry.tokens, pct };
  });

  return (
    <div data-testid={testId}>
      <Table
        variant="embedded"
        columnDefinitions={[
          { id: "stage", header: "Stage", cell: (item) => item.stage },
          {
            id: "timing",
            header: "Relative time",
            cell: (item) => (
              <ProgressBar
                value={item.pct}
                additionalInfo={`${item.ms.toFixed(1)}ms`}
                label=""
                variant="key-value"
              />
            ),
          },
          { id: "tokens", header: "Tokens", cell: (item) => (item.tokens > 0 ? item.tokens : "—") },
        ]}
        items={rows}
        sortingDisabled
      />
    </div>
  );
}
