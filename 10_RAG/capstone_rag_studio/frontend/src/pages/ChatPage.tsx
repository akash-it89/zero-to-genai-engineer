import { useEffect, useRef, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Select, { type SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import {
  api,
  ApiError,
  type ConversationMessage,
  type ConversationSummary,
  type PipelineConfig,
} from "../apiClient";
import { usePrincipal } from "../PrincipalContext";
import { testId } from "../testid";

export default function ChatPage() {
  const { principal } = usePrincipal();
  const [variants, setVariants] = useState<Record<string, PipelineConfig>>({});
  const [selectedVariant, setSelectedVariant] = useState<string>("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const variantOptions: SelectProps.Option[] = Object.keys(variants).map((name) => ({ label: name, value: name }));

  async function refreshConversations() {
    try {
      setConversations(await api.listConversations(principal));
    } catch {
      setConversations([]);
    }
  }

  useEffect(() => {
    api.listVariants(principal).then(setVariants).catch(() => setVariants({}));
    refreshConversations();
  }, [principal]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleNewConversation() {
    if (!selectedVariant) return;
    setError(null);
    try {
      const resp = await api.startConversation(principal, selectedVariant);
      setConversationId(resp.conversation_id);
      setMessages([]);
      await refreshConversations();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleResumeConversation(id: string, variantName: string) {
    setError(null);
    try {
      const resp = await api.getConversationMessages(principal, id);
      setConversationId(id);
      setSelectedVariant(variantName);
      setMessages(resp.messages);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content || !conversationId || sending) return;
    setDraft("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content, citations: [], trace_id: null, created_at: "" }]);
    setSending(true);
    try {
      const result = await api.postConversationMessage(principal, conversationId, content);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.answer, citations: result.citations, trace_id: result.trace_id, created_at: "" },
      ]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div {...testId("chat-page")}>
      <ContentLayout
        header={<Header variant="h1" description="A conversational assistant grounded in your ingested documents — remembers the last few turns.">Chat</Header>}
      >
        <SpaceBetween size="l">
          <Container>
            <SpaceBetween direction="horizontal" size="m" alignItems="end">
              <FormField label="Variant">
                <div style={{ minWidth: "260px" }} {...testId("converse-variant-select")}>
                  <Select
                    selectedOption={variantOptions.find((o) => o.value === selectedVariant) ?? null}
                    onChange={(e) => setSelectedVariant(e.detail.selectedOption.value ?? "")}
                    options={variantOptions}
                    placeholder="Select a variant…"
                    empty="No saved + indexed variants yet"
                  />
                </div>
              </FormField>
              <Button onClick={handleNewConversation} disabled={!selectedVariant} {...testId("new-conversation-button")}>
                New conversation
              </Button>
              {conversations.length > 0 && (
                <FormField label="Resume">
                  <div style={{ minWidth: "260px" }} {...testId("resume-conversation-select")}>
                    <Select
                      selectedOption={
                        conversationId
                          ? { label: conversations.find((c) => c.id === conversationId)?.variant_name ?? conversationId, value: conversationId }
                          : null
                      }
                      onChange={(e) => {
                        const id = e.detail.selectedOption.value;
                        const conv = conversations.find((c) => c.id === id);
                        if (id && conv) handleResumeConversation(id, conv.variant_name);
                      }}
                      options={conversations.map((c) => ({
                        label: `${c.variant_name} — ${new Date(c.created_at).toLocaleString()}`,
                        value: c.id,
                      }))}
                      placeholder="Resume a past conversation…"
                    />
                  </div>
                </FormField>
              )}
            </SpaceBetween>
          </Container>

          {conversationId && (
            <Container>
              <div
                {...testId("message-thread")}
                style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "50vh", overflowY: "auto", padding: "4px" }}
              >
                {messages.length === 0 && (
                  <Box color="text-status-inactive">Ask your first question below to get started.</Box>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    data-testid={`message-${m.role}-${i}`}
                    style={{
                      alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                      maxWidth: "75%",
                      background: m.role === "user" ? "#0972d3" : "#f2f3f3",
                      color: m.role === "user" ? "#ffffff" : "#16191f",
                      borderRadius: "12px",
                      padding: "10px 14px",
                    }}
                  >
                    <div>{m.content}</div>
                    {m.citations.length > 0 && (
                      <div style={{ marginTop: "6px" }}>
                        <SpaceBetween direction="horizontal" size="xs">
                          {m.citations.map((c) => (
                            <Badge key={c.chunk_id} color="grey">
                              {c.source}
                            </Badge>
                          ))}
                        </SpaceBetween>
                      </div>
                    )}
                  </div>
                ))}
                {sending && (
                  <div style={{ alignSelf: "flex-start" }}>
                    <Spinner /> <span>Thinking…</span>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              <Box margin={{ top: "m" }}>
                <SpaceBetween direction="horizontal" size="xs">
                  <div style={{ width: "480px" }}>
                    <Input
                      value={draft}
                      onChange={(e) => setDraft(e.detail.value)}
                      placeholder="Ask a follow-up question…"
                      onKeyDown={(e) => {
                        if (e.detail.key === "Enter") handleSend();
                      }}
                      {...testId("converse-input")}
                    />
                  </div>
                  <Button variant="primary" onClick={handleSend} disabled={!draft.trim() || sending} {...testId("converse-send-button")}>
                    Send
                  </Button>
                </SpaceBetween>
              </Box>
            </Container>
          )}

          {error && (
            <Alert type="error" {...testId("converse-error")}>
              {error}
            </Alert>
          )}
        </SpaceBetween>
      </ContentLayout>
    </div>
  );
}
