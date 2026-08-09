import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Select, { type SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import { api, ApiError, type OptionEntry, type OptionsCatalog, type PipelineConfig } from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { testId } from "../testid";

const CATEGORY_TO_FIELD: Record<string, keyof PipelineConfig> = {
  chunker: "chunk_strategy",
  embedding: "embedding",
  vector_store: "vector_store",
  query_transform: "query_transform",
  retrieval: "retrieval",
  post_retrieval: "post_retrieval",
  reranker: "reranker",
  generation_llm: "llm",
  orchestrator: "orchestrator",
  cache: "caching",
  guardrail: "guardrails",
};

const DEFAULT_CONFIG: PipelineConfig = {
  name: "",
  chunk_strategy: "recursive",
  chunk_size: 500,
  chunk_overlap: 60,
  embedding: "bge-small",
  vector_store: "memory",
  query_transform: "none",
  retrieval: "hybrid_rrf",
  top_k: 20,
  alpha: 0.5,
  rrf_k: 60,
  post_retrieval: "none",
  reranker: "cross_encoder",
  rerank_top_k: 5,
  llm: "gpt-4o-mini",
  temperature: 0.0,
  orchestrator: "linear",
  caching: "exact_match",
  guardrails: "light",
};

function catalogToOptions(entries: OptionEntry[]): SelectProps.Option[] {
  return entries.map((opt) => ({
    label:
      opt.label +
      (opt.reserved ? " (reserved — unavailable in v1)" : !opt.available ? " (unavailable — missing key)" : ""),
    value: opt.key,
    disabled: !opt.available,
  }));
}

export default function BuildStrategiesPage() {
  const { principal } = usePrincipal();
  const [catalog, setCatalog] = useState<OptionsCatalog>({});
  const [config, setConfig] = useState<PipelineConfig>(DEFAULT_CONFIG);
  const [variants, setVariants] = useState<Record<string, PipelineConfig>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [opts, vars] = await Promise.all([api.getOptions(principal), api.listVariants(principal)]);
    setCatalog(opts);
    setVariants(vars);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [principal]);

  function updateField(field: keyof PipelineConfig, value: string | number) {
    setConfig((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    setError(null);
    setMessage(null);
    try {
      await api.saveVariant(principal, config);
      setMessage(`Saved variant '${config.name}'.`);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleDelete(name: string) {
    setError(null);
    try {
      await api.deleteVariant(principal, name);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div {...testId("build-strategies-page")}>
      <ContentLayout
        header={<Header variant="h1" description="Compose a named strategy variant from the live Options_Catalog.">Build Strategies</Header>}
      >
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">Variant configuration</Header>}>
            <Form
              actions={
                <Button variant="primary" disabled={!config.name} onClick={handleSave} {...testId("save-variant-button")}>
                  Save Variant
                </Button>
              }
            >
              <SpaceBetween size="l">
                <FormField label="Variant name">
                  <Input
                    value={config.name}
                    onChange={(e) => updateField("name", e.detail.value)}
                    {...testId("variant-name-input")}
                  />
                </FormField>

                {Object.entries(CATEGORY_TO_FIELD).map(([category, field]) => {
                  const options = catalogToOptions(Object.values(catalog[category] ?? {}));
                  const selected = options.find((o) => o.value === String(config[field])) ?? null;
                  return (
                    <FormField key={category} label={category}>
                      <div {...testId(`selector-${category}`)}>
                        <div {...testId(`select-${category}`)}>
                          <Select
                            selectedOption={selected}
                            onChange={(e) => updateField(field, e.detail.selectedOption.value ?? "")}
                            options={options}
                          />
                        </div>
                      </div>
                    </FormField>
                  );
                })}

                <FormField label="top_k">
                  <Input
                    type="number"
                    value={String(config.top_k)}
                    onChange={(e) => updateField("top_k", Number(e.detail.value))}
                    {...testId("top-k-input")}
                  />
                </FormField>

                <FormField label="rerank_top_k">
                  <Input
                    type="number"
                    value={String(config.rerank_top_k)}
                    onChange={(e) => updateField("rerank_top_k", Number(e.detail.value))}
                    {...testId("rerank-top-k-input")}
                  />
                </FormField>
              </SpaceBetween>
            </Form>

            {message && (
              <Box margin={{ top: "m" }} {...testId("save-message")}>
                {message}
              </Box>
            )}
            {error && (
              <Box margin={{ top: "m" }}>
                <Alert type="error" {...testId("save-error")}>
                  {error}
                </Alert>
              </Box>
            )}
          </Container>

          <Container header={<Header variant="h2">Saved Variants</Header>}>
            <div {...testId("variant-list")}>
              <Table
                columnDefinitions={[
                  { id: "name", header: "Name", cell: (item: { name: string }) => item.name },
                  {
                    id: "actions",
                    header: "Actions",
                    cell: (item: { name: string }) => (
                      <Button onClick={() => handleDelete(item.name)} {...testId(`delete-variant-${item.name}`)}>
                        Delete
                      </Button>
                    ),
                  },
                ]}
                items={Object.keys(variants).map((name) => ({ name }))}
                empty={<Box textAlign="center" color="inherit">No variants saved yet.</Box>}
              />
            </div>
          </Container>
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
