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
import { api, ApiError, type PipelineConfig } from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { testId } from "../testid";

const ACCESS_LEVEL_OPTIONS: SelectProps.Option[] = [
  { label: "PUBLIC", value: "PUBLIC" },
  { label: "RESTRICTED", value: "RESTRICTED" },
  { label: "PRIVATE", value: "PRIVATE" },
];

export default function IngestPage() {
  const { principal } = usePrincipal();
  const [files, setFiles] = useState<File[]>([]);
  const [accessLevel, setAccessLevel] = useState("PUBLIC");
  const [acl, setAcl] = useState("");
  const [ingested, setIngested] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [variants, setVariants] = useState<Record<string, PipelineConfig>>({});
  const [selectedVariant, setSelectedVariant] = useState("");
  const [indexStatus, setIndexStatus] = useState<string | null>(null);

  useEffect(() => {
    api.listVariants(principal).then(setVariants).catch(() => setVariants({}));
  }, [principal]);

  const canUpload = files.length > 0;
  const variantOptions: SelectProps.Option[] = Object.keys(variants).map((name) => ({ label: name, value: name }));

  async function handleIngest() {
    setError(null);
    try {
      const resp = await api.ingest(principal, files, accessLevel, acl);
      setIngested(resp.ingested);
      setFiles([]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleBuildIndex() {
    setError(null);
    setIndexStatus(null);
    try {
      const resp = await api.buildIndex(principal, selectedVariant);
      setIndexStatus(`Indexed ${resp.chunk_count} chunks for '${resp.variant_name}'.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div {...testId("ingest-page")}>
      <ContentLayout header={<Header variant="h1" description="Upload documents and set who can access them.">Ingest Documents</Header>}>
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">Upload</Header>}>
            <Form>
              <SpaceBetween size="l">
                <FormField label="Files" controlId="file-input">
                  <input
                    id="file-input"
                    {...testId("file-input")}
                    type="file"
                    multiple
                    onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                  />
                </FormField>

                <FormField label="Access level">
                  <div {...testId("access-level-select")}>
                    <Select
                      selectedOption={ACCESS_LEVEL_OPTIONS.find((o) => o.value === accessLevel) ?? null}
                      onChange={(e) => setAccessLevel(e.detail.selectedOption.value ?? "PUBLIC")}
                      options={ACCESS_LEVEL_OPTIONS}
                    />
                  </div>
                </FormField>

                {(accessLevel === "RESTRICTED" || accessLevel === "PRIVATE") && (
                  <div {...testId("acl-controls")}>
                    <FormField label="ACL" description="Comma-separated user/role/group ids">
                      <Input
                        value={acl}
                        onChange={(e) => setAcl(e.detail.value)}
                        placeholder="e.g. hr-team, bob"
                        {...testId("acl-input")}
                      />
                    </FormField>
                  </div>
                )}

                <Button variant="primary" disabled={!canUpload} onClick={handleIngest} {...testId("ingest-button")}>
                  Upload &amp; Ingest
                </Button>
              </SpaceBetween>
            </Form>

            {ingested.length > 0 && (
              <Box margin={{ top: "m" }}>
                <ul {...testId("ingested-list")}>
                  {ingested.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </Box>
            )}

            {error && (
              <Box margin={{ top: "m" }}>
                <Alert type="error" {...testId("ingest-error")}>
                  {error}
                </Alert>
              </Box>
            )}
          </Container>

          <Container header={<Header variant="h2">Build Index</Header>}>
            <SpaceBetween size="l">
              <FormField label="Variant">
                <div {...testId("index-variant-select")}>
                  <Select
                    selectedOption={variantOptions.find((o) => o.value === selectedVariant) ?? null}
                    onChange={(e) => setSelectedVariant(e.detail.selectedOption.value ?? "")}
                    options={variantOptions}
                    placeholder="Select a variant…"
                    empty="No saved variants yet"
                  />
                </div>
              </FormField>
              <Button disabled={!selectedVariant} onClick={handleBuildIndex} {...testId("build-index-button")}>
                Build Index
              </Button>
              {indexStatus && (
                <Box {...testId("index-status")} color="text-status-success">
                  {indexStatus}
                </Box>
              )}
            </SpaceBetween>
          </Container>
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
