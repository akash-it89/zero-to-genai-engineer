import { useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "";

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hi — I’m the Lauki Support Copilot (Strands on AgentCore + Bedrock Guardrails). Ask about activation, eSIM, or plans.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [threadId] = useState(() => crypto.randomUUID());
  const actorId = "react-user";

  const apiLabel = useMemo(
    () => (API_BASE ? API_BASE : "same-origin / local proxy"),
    []
  );

  async function send(e) {
    e.preventDefault();
    const prompt = input.trim();
    if (!prompt || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: prompt }]);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          actor_id: actorId,
          thread_id: threadId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || res.statusText);
      }
      setMessages((m) => [...m, { role: "assistant", text: data.result }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `Error: ${err.message}`, error: true },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="hero">
        <h1>Lauki Support</h1>
        <p>
          React UI → API → AgentCore Runtime (Strands) with Amazon Bedrock +
          Guardrails.
        </p>
      </header>

      <section className="panel">
        <div className="messages">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`msg ${m.role}${m.error ? " error" : ""}`}
            >
              {m.text}
            </div>
          ))}
        </div>
        <form className="composer" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="How do I activate a new SIM?"
            disabled={busy}
          />
          <button type="submit" disabled={busy}>
            {busy ? "…" : "Send"}
          </button>
        </form>
      </section>

      <footer className="meta">
        <span className="chip">thread {threadId.slice(0, 8)}</span>
        <span className="chip">API {apiLabel}</span>
      </footer>
    </div>
  );
}
