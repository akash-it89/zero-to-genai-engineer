import { useState } from "react";
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
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { api, ApiError, type AccessPolicyResponse } from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { testId } from "../testid";

const ACCESS_LEVEL_OPTIONS: SelectProps.Option[] = [
  { label: "PUBLIC", value: "PUBLIC" },
  { label: "RESTRICTED", value: "RESTRICTED" },
  { label: "PRIVATE", value: "PRIVATE" },
];

const STATUS_TYPE: Record<string, "success" | "warning" | "error"> = {
  PUBLIC: "success",
  RESTRICTED: "warning",
  PRIVATE: "error",
};

export default function GovernancePage() {
  const { principal, setPrincipal } = usePrincipal();
  const [principalIdInput, setPrincipalIdInput] = useState(principal.id);
  const [rolesInput, setRolesInput] = useState(principal.roles.join(","));

  const [docId, setDocId] = useState("");
  const [policy, setPolicy] = useState<AccessPolicyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSwitchPrincipal() {
    setPrincipal({
      id: principalIdInput,
      roles: rolesInput
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean),
    });
  }

  async function handleLoadPolicy() {
    setError(null);
    try {
      const p = await api.getPolicy(principal, docId);
      setPolicy(p);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleSavePolicy() {
    if (!policy) return;
    setError(null);
    try {
      await api.setPolicy(principal, docId, policy);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div {...testId("governance-page")}>
      <ContentLayout header={<Header variant="h1" description="Switch the Acting Principal and manage document access policies.">Governance</Header>}>
        <SpaceBetween size="l">
          <Container header={<Header variant="h2">Acting Principal</Header>}>
            <div {...testId("principal-switcher")}>
              <Form actions={<Button onClick={handleSwitchPrincipal} {...testId("switch-principal-button")}>Switch</Button>}>
                <SpaceBetween size="l">
                  <FormField label="Principal id">
                    <Input value={principalIdInput} onChange={(e) => setPrincipalIdInput(e.detail.value)} {...testId("principal-id-input")} />
                  </FormField>
                  <FormField label="Roles" description="Comma-separated">
                    <Input value={rolesInput} onChange={(e) => setRolesInput(e.detail.value)} {...testId("principal-roles-input")} />
                  </FormField>
                </SpaceBetween>
              </Form>
              <Box margin={{ top: "m" }} {...testId("current-principal")}>
                Acting as: {principal.id} ({principal.roles.join(", ") || "no roles"})
              </Box>
            </div>
          </Container>

          <Container header={<Header variant="h2">Access Policy</Header>}>
            <div {...testId("policy-editor")}>
              <SpaceBetween size="l">
                <FormField label="Document id">
                  <Input value={docId} onChange={(e) => setDocId(e.detail.value)} {...testId("doc-id-input")} />
                </FormField>
                <Button disabled={!docId} onClick={handleLoadPolicy} {...testId("load-policy-button")}>
                  Load
                </Button>

                {policy && (
                  <div {...testId("policy-form")}>
                    <SpaceBetween size="l">
                      <Box>
                        Current level: <StatusIndicator type={STATUS_TYPE[policy.access_level]}>{policy.access_level}</StatusIndicator>
                      </Box>
                      <FormField label="Access level">
                        <div {...testId("policy-level-select")}>
                          <Select
                            selectedOption={ACCESS_LEVEL_OPTIONS.find((o) => o.value === policy.access_level) ?? null}
                            onChange={(e) =>
                              setPolicy({
                                ...policy,
                                access_level: (e.detail.selectedOption.value as AccessPolicyResponse["access_level"]) ?? "PRIVATE",
                              })
                            }
                            options={ACCESS_LEVEL_OPTIONS}
                          />
                        </div>
                      </FormField>
                      <FormField label="ACL" description="Comma-separated">
                        <Input
                          value={policy.acl.join(",")}
                          onChange={(e) => setPolicy({ ...policy, acl: e.detail.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                          {...testId("policy-acl-input")}
                        />
                      </FormField>
                      <Button onClick={handleSavePolicy} {...testId("save-policy-button")}>
                        Save
                      </Button>
                    </SpaceBetween>
                  </div>
                )}

                {error && (
                  <Alert type="error" {...testId("governance-error")}>
                    {error}
                  </Alert>
                )}
              </SpaceBetween>
            </div>
          </Container>
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
