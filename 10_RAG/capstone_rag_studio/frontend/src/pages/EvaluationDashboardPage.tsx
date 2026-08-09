import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Checkbox from "@cloudscape-design/components/checkbox";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import ProgressBar from "@cloudscape-design/components/progress-bar";
import Select, { type SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import Textarea from "@cloudscape-design/components/textarea";
import {
  api,
  ApiError,
  type MetricScoresResponse,
  type PipelineConfig,
  type RetrievalEvaluationResponse,
} from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { testId } from "../testid";

const DEFAULT_RETRIEVAL_GOLDEN_SET = JSON.stringify(
  [
    {
      question: "What is the capital of France?",
      expected_sources: ["france_facts.pdf"],
      query_type: "semantic",
    },
    {
      question: "capital France",
      expected_sources: ["france_facts.pdf"],
      query_type: "keyword",
    },
  ],
  null,
  2,
);

const RETRIEVAL_METRIC_ORDER = ["r@1", "r@3", "mrr@10", "ndcg@3"];
const RETRIEVAL_METRIC_LABELS: Record<string, string> = {
  "r@1": "R@1",
  "r@3": "R@3",
  "mrr@10": "MRR@10",
  "ndcg@3": "NDCG@3",
};

const DEFAULT_GOLDEN_SET = JSON.stringify(
  [
    {
      id: "s1",
      question: "What is the capital of France?",
      answer: "Paris.",
      contexts: ["Paris is the capital of France."],
      reference: "Paris",
    },
  ],
  null,
  2,
);

const FRAMEWORK_OPTIONS: SelectProps.Option[] = [
  { label: "RAGAS", value: "ragas" },
  { label: "DeepEval", value: "deepeval" },
];

const AVAILABLE_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "geval"];

export default function EvaluationDashboardPage() {
  const { principal } = usePrincipal();
  const [goldenSetText, setGoldenSetText] = useState(DEFAULT_GOLDEN_SET);
  const [framework, setFramework] = useState("ragas");
  const [metrics, setMetrics] = useState<string[]>(["faithfulness", "answer_relevancy"]);
  const [result, setResult] = useState<MetricScoresResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [variants, setVariants] = useState<Record<string, PipelineConfig>>({});
  const [selectedVariants, setSelectedVariants] = useState<string[]>([]);
  const [retrievalGoldenSetText, setRetrievalGoldenSetText] = useState(DEFAULT_RETRIEVAL_GOLDEN_SET);
  const [retrievalResult, setRetrievalResult] = useState<RetrievalEvaluationResponse | null>(null);
  const [retrievalError, setRetrievalError] = useState<string | null>(null);

  useEffect(() => {
    api.listVariants(principal).then(setVariants).catch(() => setVariants({}));
  }, [principal]);

  function toggleMetric(metric: string) {
    setMetrics((prev) => (prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric]));
  }

  function toggleVariant(name: string) {
    setSelectedVariants((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]));
  }

  async function handleRun() {
    setError(null);
    setResult(null);
    try {
      const samples = JSON.parse(goldenSetText);
      const scores = await api.evaluateGolden(principal, samples, framework, metrics);
      setResult(scores);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleRunRetrieval() {
    setRetrievalError(null);
    setRetrievalResult(null);
    try {
      const goldenSet = JSON.parse(retrievalGoldenSetText);
      const scores = await api.evaluateRetrieval(principal, goldenSet, selectedVariants);
      setRetrievalResult(scores);
    } catch (e) {
      setRetrievalError(e instanceof ApiError ? e.message : String(e));
    }
  }

  const rows = result
    ? Object.entries(result.scores).map(([metric, score]) => ({
        metric,
        score,
        passed: result.passed[metric],
        reason: result.reasons[metric],
      }))
    : [];

  return (
    <div {...testId("evaluation-dashboard-page")}>
      <ContentLayout header={<Header variant="h1" description="Score a golden set with RAGAS or DeepEval.">Evaluation Dashboard</Header>}>
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">Run an evaluation</Header>}>
            <Form actions={<Button variant="primary" onClick={handleRun} {...testId("run-evaluation-button")}>Run</Button>}>
              <SpaceBetween size="l">
                <FormField label="Golden set (JSON array)">
                  <div {...testId("golden-set-textarea")}>
                    <Textarea value={goldenSetText} onChange={(e) => setGoldenSetText(e.detail.value)} rows={10} />
                  </div>
                </FormField>

                <FormField label="Framework">
                  <div {...testId("framework-select")}>
                    <Select
                      selectedOption={FRAMEWORK_OPTIONS.find((o) => o.value === framework) ?? null}
                      onChange={(e) => setFramework(e.detail.selectedOption.value ?? "ragas")}
                      options={FRAMEWORK_OPTIONS}
                    />
                  </div>
                </FormField>

                <FormField label="Metrics">
                  <div {...testId("metric-checkboxes")}>
                    <SpaceBetween direction="horizontal" size="m">
                      {AVAILABLE_METRICS.map((m) => (
                        <Checkbox
                          key={m}
                          checked={metrics.includes(m)}
                          onChange={() => toggleMetric(m)}
                          {...testId(`metric-checkbox-${m}`)}
                        >
                          {m}
                        </Checkbox>
                      ))}
                    </SpaceBetween>
                  </div>
                </FormField>
              </SpaceBetween>
            </Form>

            {error && (
              <Box margin={{ top: "m" }}>
                <Alert type="error" {...testId("evaluation-error")}>
                  {error}
                </Alert>
              </Box>
            )}
          </Container>

          {result && (
            <Container header={<Header variant="h2">Results</Header>}>
              <div {...testId("evaluation-results")}>
                <div {...testId("evaluation-table")}>
                  <Table
                    columnDefinitions={[
                      {
                        id: "metric",
                        header: "Metric",
                        cell: (item) => <span {...testId(`metric-row-${item.metric}`)}>{item.metric}</span>,
                      },
                      {
                        id: "score",
                        header: "Score",
                        cell: (item) => (
                          <div {...testId(`metric-bar-${item.metric}`)}>
                            <ProgressBar value={Math.max(0, Math.min(1, item.score)) * 100} additionalInfo={item.score.toFixed(3)} label="" />
                          </div>
                        ),
                      },
                      ...(framework === "deepeval"
                        ? [
                            {
                              id: "pass",
                              header: "Pass/Fail",
                              cell: (item: (typeof rows)[number]) => (
                                <div {...testId(`metric-pass-${item.metric}`)}>
                                  <StatusIndicator type={item.passed ? "success" : "error"}>
                                    {item.passed ? "PASS" : "FAIL"}
                                  </StatusIndicator>
                                </div>
                              ),
                            },
                            {
                              id: "reason",
                              header: "Reason",
                              cell: (item: (typeof rows)[number]) => (
                                <span {...testId(`metric-reason-${item.metric}`)}>{item.reason}</span>
                              ),
                            },
                          ]
                        : []),
                    ]}
                    items={rows}
                    sortingDisabled
                  />
                </div>
                {result.excluded_reference_dependent.length > 0 && (
                  <Box margin={{ top: "m" }} color="text-status-inactive" {...testId("excluded-records")}>
                    Excluded from reference-dependent metrics (no ground truth): {result.excluded_reference_dependent.join(", ")}
                  </Box>
                )}
              </div>
            </Container>
          )}

          <Container
            header={
              <Header
                variant="h2"
                description="Score R@1 / R@3 / MRR@10 / NDCG@3 for one or more saved variants against a golden set — the ablation-matrix workflow from EVALUATION_METHODOLOGY.md."
              >
                Retrieval Metrics (Ablation)
              </Header>
            }
          >
            <Form actions={<Button variant="primary" onClick={handleRunRetrieval} {...testId("run-retrieval-eval-button")}>Run Retrieval Eval</Button>}>
              <SpaceBetween size="l">
                <FormField
                  label="Golden set (JSON array)"
                  description='Each item: {"question", "expected_sources": [doc filenames], "query_type" (optional, e.g. "keyword"/"semantic")}'
                >
                  <div {...testId("retrieval-golden-set-textarea")}>
                    <Textarea value={retrievalGoldenSetText} onChange={(e) => setRetrievalGoldenSetText(e.detail.value)} rows={10} />
                  </div>
                </FormField>

                <FormField label="Variants" description="None selected = all saved variants">
                  <div {...testId("retrieval-variant-checkboxes")}>
                    <SpaceBetween size="xs">
                      {Object.keys(variants).length === 0 && (
                        <Box color="text-status-inactive">No saved variants yet — build one on Build Strategies first.</Box>
                      )}
                      {Object.keys(variants).map((name) => (
                        <Checkbox
                          key={name}
                          checked={selectedVariants.includes(name)}
                          onChange={() => toggleVariant(name)}
                          {...testId(`retrieval-variant-checkbox-${name}`)}
                        >
                          {name}
                        </Checkbox>
                      ))}
                    </SpaceBetween>
                  </div>
                </FormField>
              </SpaceBetween>
            </Form>

            {retrievalError && (
              <Box margin={{ top: "m" }}>
                <Alert type="error" {...testId("retrieval-evaluation-error")}>
                  {retrievalError}
                </Alert>
              </Box>
            )}

            {retrievalResult && (
              <Box margin={{ top: "l" }}>
                <SpaceBetween size="l">
                  <div {...testId("retrieval-results-table")}>
                    <Table
                      header={<Header variant="h3">Overall</Header>}
                      columnDefinitions={[
                        {
                          id: "variant",
                          header: "Variant",
                          cell: (item: { variant: string } & Record<string, number>) => (
                            <span {...testId(`retrieval-variant-row-${item.variant}`)}>{item.variant}</span>
                          ),
                        },
                        ...RETRIEVAL_METRIC_ORDER.map((m) => ({
                          id: m,
                          header: RETRIEVAL_METRIC_LABELS[m],
                          cell: (item: { variant: string } & Record<string, number>) => (
                            <span {...testId(`retrieval-metric-${item.variant}-${m}`)}>{(item[m] ?? 0).toFixed(3)}</span>
                          ),
                        })),
                      ]}
                      items={Object.entries(retrievalResult.results).map(([variant, m]) => ({
                        variant,
                        ...m.overall,
                      }))}
                      sortingDisabled
                    />
                  </div>

                  {Object.entries(retrievalResult.results).some(([, m]) => Object.keys(m.by_query_type).length > 0) && (
                    <div {...testId("retrieval-by-query-type")}>
                      <SpaceBetween size="m">
                        <Header variant="h3">By query type</Header>
                        {Object.entries(retrievalResult.results).map(([variant, m]) =>
                          Object.keys(m.by_query_type).length > 0 ? (
                            <div key={variant} {...testId(`retrieval-query-type-table-${variant}`)}>
                              <Table
                                header={<Header variant="h3">{variant}</Header>}
                                columnDefinitions={[
                                  {
                                    id: "query_type",
                                    header: "Query type",
                                    cell: (item: { query_type: string } & Record<string, number>) => item.query_type,
                                  },
                                  ...RETRIEVAL_METRIC_ORDER.map((mName) => ({
                                    id: mName,
                                    header: RETRIEVAL_METRIC_LABELS[mName],
                                    cell: (item: { query_type: string } & Record<string, number>) =>
                                      (item[mName] ?? 0).toFixed(3),
                                  })),
                                ]}
                                items={Object.entries(m.by_query_type).map(([queryType, scores]) => ({
                                  query_type: queryType,
                                  ...scores,
                                }))}
                                sortingDisabled
                              />
                            </div>
                          ) : null,
                        )}
                      </SpaceBetween>
                    </div>
                  )}

                  {Object.keys(retrievalResult.errors).length > 0 && (
                    <div {...testId("retrieval-errors")}>
                      <SpaceBetween size="xs">
                        {Object.entries(retrievalResult.errors).map(([variant, message]) => (
                          <Alert key={variant} type="error" header={variant}>
                            {message}
                          </Alert>
                        ))}
                      </SpaceBetween>
                    </div>
                  )}
                </SpaceBetween>
              </Box>
            )}
          </Container>
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
