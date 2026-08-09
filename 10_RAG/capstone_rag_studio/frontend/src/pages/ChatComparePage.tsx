import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Checkbox from "@cloudscape-design/components/checkbox";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Toggle from "@cloudscape-design/components/toggle";
import { api, ApiError, type AnswerResult, type MetricScoresResponse, type PipelineConfig, type Trace } from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { StageRail } from "../StageRail";
import { testId } from "../testid";

export default function ChatComparePage() {
  const { principal } = usePrincipal();
  const [variants, setVariants] = useState<Record<string, PipelineConfig>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState<Record<string, AnswerResult>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [autoEvaluate, setAutoEvaluate] = useState(false);
  const [evaluations, setEvaluations] = useState<Record<string, MetricScoresResponse>>({});
  const [traces, setTraces] = useState<Record<string, Trace>>({});
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    api.listVariants(principal).then(setVariants).catch(() => setVariants({}));
  }, [principal]);

  function toggleVariant(name: string) {
    setSelected((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]));
  }

  async function evaluateAnswer(name: string, result: AnswerResult) {
    const sample = {
      id: name,
      question,
      answer: result.answer,
      contexts: (result.reranked_chunks as Array<{ text: string }>).map((c) => c.text),
    };
    const scores = await api.evaluateLive(principal, [sample], "ragas", ["faithfulness", "answer_relevancy"]);
    setEvaluations((prev) => ({ ...prev, [name]: scores }));
  }

  async function handleAsk() {
    setRequestError(null);
    setResults({});
    setErrors({});
    setEvaluations({});
    try {
      const variantNames = selected.length > 0 ? selected : undefined;
      const resp = await api.chat(principal, question, variantNames);
      setResults(resp.results);
      setErrors(resp.errors);
      if (autoEvaluate) {
        for (const [name, result] of Object.entries(resp.results)) {
          await evaluateAnswer(name, result);
        }
      }
    } catch (e) {
      setRequestError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleViewTrace(name: string, traceId: string) {
    const trace = await api.getTrace(principal, traceId);
    setTraces((prev) => ({ ...prev, [name]: trace }));
  }

  const cardCount = Object.keys(results).length + Object.keys(errors).length;

  return (
    <div {...testId("chat-compare-page")}>
      <ContentLayout header={<Header variant="h1" description="Ask a question against one or more saved variants and compare the cited answers.">Chat &amp; Compare</Header>}>
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">Ask</Header>}>
            <SpaceBetween size="l">
              <FormField label="Variants" description="None selected = all saved variants">
                <div {...testId("variant-checkboxes")}>
                  <SpaceBetween size="xs">
                    {Object.keys(variants).length === 0 && (
                      <Box color="text-status-inactive">No saved variants yet — build one on Build Strategies first.</Box>
                    )}
                    {Object.keys(variants).map((name) => (
                      <Checkbox
                        key={name}
                        checked={selected.includes(name)}
                        onChange={() => toggleVariant(name)}
                        {...testId(`variant-checkbox-${name}`)}
                      >
                        {name}
                      </Checkbox>
                    ))}
                  </SpaceBetween>
                </div>
              </FormField>

              <FormField label="Question">
                <Input value={question} onChange={(e) => setQuestion(e.detail.value)} {...testId("question-input")} />
              </FormField>

              <Toggle checked={autoEvaluate} onChange={(e) => setAutoEvaluate(e.detail.checked)} {...testId("auto-evaluate-toggle")}>
                Auto-evaluate
              </Toggle>

              <Button variant="primary" disabled={!question} onClick={handleAsk} {...testId("ask-button")}>
                Ask
              </Button>
            </SpaceBetween>

            {requestError && (
              <Box margin={{ top: "m" }}>
                <Alert type="error" {...testId("chat-error")}>
                  {requestError}
                </Alert>
              </Box>
            )}
          </Container>

          <div {...testId("results-grid")}>
            <ColumnLayout columns={Math.max(1, Math.min(cardCount, 3))} borders="vertical">
              {Object.entries(results).map(([name, result]) => (
                <div key={name} {...testId(`result-card-${name}`)}>
                  <SpaceBetween size="m">
                    <Header variant="h3">
                      <StatusIndicator type="success">{name}</StatusIndicator>
                    </Header>
                    <Box {...testId(`answer-${name}`)}>{result.answer}</Box>
                    <Box color="text-body-secondary" {...testId(`filtered-count-${name}`)}>
                      Governance filtered: {result.governance_filtered_count}
                    </Box>

                    <StageRail timing={result.per_stage_timing} />
                    <ul {...testId(`timing-${name}`)} style={{ display: "none" }}>
                      {Object.entries(result.per_stage_timing).map(([stage, ms]) => (
                        <li key={stage}>
                          {stage}: {ms.toFixed(1)}ms
                        </li>
                      ))}
                    </ul>

                    {result.citations.length > 0 && (
                      <div {...testId(`citations-${name}`)}>
                        <SpaceBetween direction="horizontal" size="xs">
                          {result.citations.map((c) => (
                            <Badge key={c.chunk_id} color="blue">
                              {c.source}
                            </Badge>
                          ))}
                        </SpaceBetween>
                      </div>
                    )}

                    <SpaceBetween direction="horizontal" size="xs">
                      <Button onClick={() => evaluateAnswer(name, result)} {...testId(`evaluate-button-${name}`)}>
                        Evaluate
                      </Button>
                      <Button onClick={() => handleViewTrace(name, result.trace_id)} {...testId(`trace-button-${name}`)}>
                        View Trace
                      </Button>
                    </SpaceBetween>

                    {evaluations[name] && (
                      <div {...testId(`evaluation-${name}`)}>
                        <SpaceBetween size="xs">
                          {Object.entries(evaluations[name].scores).map(([metric, score]) => (
                            <Box key={metric}>
                              {metric}: {score.toFixed(2)}
                            </Box>
                          ))}
                        </SpaceBetween>
                      </div>
                    )}

                    {traces[name] && (
                      <>
                        <StageRail stages={traces[name].stages} />
                        <ol {...testId(`trace-${name}`)} style={{ display: "none" }}>
                          {traces[name].stages.map((s) => (
                            <li key={s.stage}>
                              {s.stage} — {s.elapsed_ms.toFixed(1)}ms, tokens={s.token_usage}
                            </li>
                          ))}
                        </ol>
                      </>
                    )}
                  </SpaceBetween>
                </div>
              ))}
              {Object.entries(errors).map(([name, message]) => (
                <div key={name} {...testId(`error-card-${name}`)}>
                  <SpaceBetween size="m">
                    <Header variant="h3">
                      <StatusIndicator type="error">{name}</StatusIndicator>
                    </Header>
                    <Alert type="error">{message}</Alert>
                  </SpaceBetween>
                </div>
              ))}
            </ColumnLayout>
          </div>
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
