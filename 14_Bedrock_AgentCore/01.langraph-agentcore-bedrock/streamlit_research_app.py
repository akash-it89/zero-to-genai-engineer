"""
AgentCore Research console — telemetry-desk UI over InvokeAgentRuntime.

- Sample / typed prompts appear immediately as user bubbles
- Answer tokens stream inside the assistant bubble (st.write_stream)
- Live stack constellation, session sparklines, interactive tool timeline

Run:
  export AWS_PROFILE=inceptez
  export RESEARCH_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:899736802567:runtime/langgraph_research_graph-ZsDIkv2WYd"
  .venv/bin/streamlit run streamlit_research_app.py --server.port 8502
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import uuid
from typing import Any, Iterator

import boto3
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:899736802567:"
    "runtime/langgraph_research_graph-ZsDIkv2WYd"
)

SUGGESTIONS = [
    {
        "emoji": "◈",
        "title": "Stack map",
        "prompt": "What is AgentCore Runtime vs Memory vs Gateway?",
        "hint": "Concepts",
    },
    {
        "emoji": "↯",
        "title": "Tools combo",
        "prompt": "What’s the weather in Chennai, and what is 15*8+3?",
        "hint": "MCP + calc",
    },
    {
        "emoji": "◎",
        "title": "Identity → MCP",
        "prompt": "Search docs: how does Identity authenticate to MCP?",
        "hint": "RAG",
    },
    {
        "emoji": "▤",
        "title": "FAQ plans",
        "prompt": "What Lauki phone plans are in the FAQ?",
        "hint": "RAG",
    },
    {
        "emoji": "⬡",
        "title": "Live browse",
        "prompt": (
            "Browse https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/"
            "browser-tool.html and summarize Browser in 5 bullets."
        ),
        "hint": "Browser",
    },
]

STACK_HELP = {
    "Runtime": "LangGraph container. This UI only calls InvokeAgentRuntime.",
    "Memory": "Persists turns by actor_id + thread_id.",
    "Gateway": "Managed MCP HTTPS front for Lambda tools.",
    "MCP": "JSON-RPC tools loaded into the agent.",
    "Identity": "Cognito M2M OAuth via gateway-cognito-m2m.",
    "RAG": "search_docs over packaged knowledge + FAQ.",
    "Browser": "browse_url — AgentCore cloud Chromium + Playwright.",
}

# Telemetry desk tokens (must match injected CSS)
STATUS_COLOR = {
    "on": "#0f766e",
    "off": "#94a3b8",
    "pending": "#b45309",
}


def _region_from_arn(arn: str) -> str:
    m = re.match(r"^arn:aws:bedrock-agentcore:([a-z0-9-]+):", arn)
    return m.group(1) if m else "us-east-1"


def inject_theme() -> None:
    """Scoped visual system — Streamlit chrome + chat + motion."""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
}
.stApp {
  background:
    radial-gradient(1200px 600px at 12% -10%, #d7ebe7 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #f3e7d8 0%, transparent 50%),
    linear-gradient(180deg, #eef1f4 0%, #e8ecf1 100%);
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #141820 0%, #1c2430 55%, #162029 100%) !important;
  border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6,
[data-testid="stSidebar"] .stMarkdown {
  color: #e8eef2 !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
  color: #9db0bf !important;
}
/* Inputs: dark field + light text (never inherit sidebar ink onto white widgets) */
[data-testid="stSidebar"] div[data-testid="stTextInput"] input,
[data-testid="stSidebar"] div[data-testid="stTextArea"] textarea,
[data-testid="stSidebar"] div[data-baseweb="input"] input,
[data-testid="stSidebar"] div[data-baseweb="base-input"] input,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
  color: #f1f5f9 !important;
  -webkit-text-fill-color: #f1f5f9 !important;
  caret-color: #2dd4bf !important;
  background-color: #0f141b !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  border-radius: 10px !important;
}
[data-testid="stSidebar"] div[data-testid="stTextInput"] input:disabled,
[data-testid="stSidebar"] input:disabled {
  color: #94a3b8 !important;
  -webkit-text-fill-color: #94a3b8 !important;
  opacity: 1 !important;
  background-color: #151b24 !important;
}
[data-testid="stSidebar"] div[data-testid="stTextInput"] label,
[data-testid="stSidebar"] div[data-testid="stTextArea"] label {
  color: #9db0bf !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  color: #e8eef2 !important;
  border-radius: 12px;
  text-align: left;
  font-weight: 500;
  transition: border-color .18s ease, background .18s ease, transform .18s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
  border-color: #2dd4bf;
  background: rgba(45,212,191,0.10);
  transform: translateY(-1px);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0f766e, #0d9488);
  border: none;
  font-weight: 600;
}
/* Keep expanders in the main column light; sidebar ones stay dark */
section.main div[data-testid="stExpander"] {
  border: 1px solid rgba(20,24,32,0.08);
  border-radius: 14px;
  background: rgba(255,255,255,0.65);
}
[data-testid="stSidebar"] div[data-testid="stExpander"] {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  border-radius: 12px !important;
}
[data-testid="stSidebar"] div[data-testid="stExpander"] details summary,
[data-testid="stSidebar"] div[data-testid="stExpander"] details summary span {
  color: #e8eef2 !important;
}
[data-testid="stSidebar"] code,
[data-testid="stSidebar"] .stMarkdown code {
  display: inline-block;
  max-width: 100%;
  white-space: normal !important;
  word-break: break-word !important;
  overflow-wrap: anywhere !important;
  background: rgba(255,255,255,0.08) !important;
  color: #9fe8dc !important;
  border: 1px solid rgba(45,212,191,0.25);
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 10px !important;
  line-height: 1.35;
}
[data-testid="stSidebar"] .stCaption {
  word-break: break-word;
  overflow-wrap: anywhere;
}
section.main .block-container {
  max-width: 920px;
  padding-top: 1.1rem;
  padding-bottom: 5rem;
}
div[data-testid="stChatMessage"] {
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(20,24,32,0.06);
  border-radius: 18px;
  padding: 0.55rem 0.85rem;
  backdrop-filter: blur(8px);
  box-shadow: 0 10px 30px rgba(20,24,32,0.04);
  margin-bottom: 0.65rem;
}
div[data-testid="stChatInput"] textarea {
  border-radius: 16px !important;
}
div[data-testid="stMetric"] {
  background: #fff;
  border: 1px solid rgba(20,24,32,0.06);
  border-radius: 14px;
  padding: 0.55rem 0.75rem;
}
.ac-hero {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin-bottom: 1.1rem;
}
.ac-kicker {
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
  color: #0f766e; font-weight: 500; margin-bottom: 4px;
}
.ac-title {
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.8rem, 3vw, 2.35rem);
  font-weight: 700; letter-spacing: -0.02em; color: #141820;
  line-height: 1.1; margin: 0;
}
.ac-sub { color: #5b6b7c; font-size: 0.95rem; margin-top: 6px; max-width: 38rem; }
.ac-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.ac-chip {
  font-family: "IBM Plex Mono", monospace; font-size: 11px;
  padding: 6px 10px; border-radius: 999px;
  background: #fff; border: 1px solid rgba(20,24,32,0.08);
  color: #334155; box-shadow: 0 1px 0 rgba(255,255,255,0.8) inset;
}
.ac-chip strong { color: #0f766e; font-weight: 600; }
.ac-empty {
  border: 1px dashed rgba(15,118,110,0.35);
  border-radius: 20px; padding: 1.25rem 1.35rem;
  background: linear-gradient(145deg, rgba(255,255,255,0.9), rgba(215,235,231,0.45));
  margin: 0.4rem 0 1.2rem;
}
.ac-empty h3 {
  font-family: "Fraunces", Georgia, serif; margin: 0 0 0.35rem; font-size: 1.25rem;
}
.ac-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px; margin-top: 0.9rem;
}
.ac-card {
  background: #fff; border: 1px solid rgba(20,24,32,0.07);
  border-radius: 14px; padding: 12px 12px 10px; min-height: 88px;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.ac-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(20,24,32,0.08);
  border-color: rgba(15,118,110,0.35);
}
.ac-card .sym {
  font-size: 1.1rem; color: #0f766e; margin-bottom: 6px;
  font-family: "IBM Plex Mono", monospace;
}
.ac-card .t { font-weight: 600; font-size: 0.92rem; color: #141820; }
.ac-card .h {
  font-family: "IBM Plex Mono", monospace; font-size: 10px;
  letter-spacing: .08em; text-transform: uppercase; color: #7a8a9a; margin-top: 4px;
}
.ac-side-brand {
  font-family: "Fraunces", Georgia, serif; font-size: 1.35rem;
  font-weight: 700; letter-spacing: -0.02em; margin-bottom: 2px;
}
.ac-side-meta {
  font-family: "IBM Plex Mono", monospace; font-size: 10px;
  letter-spacing: .12em; text-transform: uppercase; color: #7dd3c7 !important;
  margin-bottom: 14px;
}
.ac-last-run {
  margin-top: 10px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.10);
}
.ac-last-run .lbl {
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  color: #7dd3c7; margin-bottom: 8px;
}
.ac-last-run .metrics {
  font-family: "IBM Plex Mono", monospace;
  font-size: 12px; color: #e8eef2; line-height: 1.45;
  margin-bottom: 10px;
}
.ac-last-run .tags {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.ac-last-run .tag {
  font-family: "IBM Plex Mono", monospace;
  font-size: 10px; color: #cfe8e3;
  background: rgba(45,212,191,0.12);
  border: 1px solid rgba(45,212,191,0.28);
  border-radius: 999px; padding: 4px 8px;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}
@keyframes ac-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
.ac-dot-pending { animation: ac-pulse 1.4s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .ac-dot-pending { animation: none; }
  .ac-card:hover, [data-testid="stSidebar"] .stButton > button:hover { transform: none; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def stream_research_runtime(
    *,
    arn: str,
    prompt: str,
    actor_id: str,
    thread_id: str,
    region: str,
    runtime_session_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    client = boto3.client("bedrock-agentcore", region_name=region)
    # Reuse the same Runtime session across turns — a new UUID each call
    # forces a cold microVM (~10–16s). Sticky session ≈ 1–2s warm path.
    session_id = runtime_session_id or str(uuid.uuid4())
    if len(session_id) < 33:
        session_id = f"{session_id}-{uuid.uuid4().hex}"[:64]
    payload = json.dumps(
        {"prompt": prompt, "actor_id": actor_id, "thread_id": thread_id}
    ).encode("utf-8")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        runtimeUserId=(actor_id or "streamlit-user")[:128],
        payload=payload,
        qualifier="DEFAULT",
    )
    ctype = (response.get("contentType") or "").lower()
    body = response.get("response") or response.get("body")

    if "text/event-stream" in ctype and hasattr(body, "iter_lines"):
        for line in body.iter_lines(chunk_size=1):
            if not line:
                continue
            text = (
                line.decode("utf-8", errors="replace")
                if isinstance(line, (bytes, bytearray))
                else str(line)
            )
            if text.startswith("data: "):
                text = text[6:]
            text = text.strip()
            if not text or text == "[DONE]":
                continue
            try:
                evt = json.loads(text)
            except json.JSONDecodeError:
                yield {"event": "progress", "message": text[:400]}
                continue
            if isinstance(evt, dict):
                evt["_session_id"] = session_id
                yield evt
        return

    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    data = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(data, dict):
        data["_session_id"] = session_id
        if data.get("event") != "final" and "result" in data:
            result = str(data.get("result") or "")
            for i in range(0, len(result), 12):
                yield {"event": "token", "delta": result[i : i + 12]}
            yield {
                "event": "final",
                **data,
                "metrics": data.get("metrics") or {},
                "usage": data.get("usage") or {},
            }
        else:
            yield data


def stack_state(stack: dict | None) -> list[tuple[str, str]]:
    s = stack or {}
    probed = bool(s.get("_probed"))

    def flag(key: str) -> str:
        if not probed and key in ("gateway", "mcp", "identity"):
            return "pending"
        return "on" if bool(s.get(key)) else "off"

    return [
        ("Runtime", "on"),
        ("Memory", "on" if s.get("memory", True) else "off"),
        ("Gateway", flag("gateway")),
        ("MCP", flag("mcp")),
        ("Identity", flag("identity")),
        ("RAG", "on" if s.get("rag", True) else "off"),
        ("Browser", "on" if s.get("browser") else ("pending" if not probed else "off")),
    ]


def constellation_html(stack: dict | None, *, dark: bool = True) -> str:
    """Interactive SVG of AgentCore capabilities — signature visual."""
    nodes = stack_state(stack)
    # Layout positions (viewBox 0..320 x 0..200)
    coords = {
        "Runtime": (160, 28),
        "Memory": (56, 78),
        "Gateway": (264, 78),
        "Identity": (56, 148),
        "MCP": (160, 118),
        "RAG": (264, 148),
        "Browser": (160, 188),
    }
    edges = [
        ("Runtime", "Memory"),
        ("Runtime", "Gateway"),
        ("Runtime", "MCP"),
        ("Gateway", "MCP"),
        ("Identity", "Gateway"),
        ("MCP", "RAG"),
        ("Runtime", "Browser"),
    ]
    status = {n: s for n, s in nodes}
    bg = "#0f141b" if dark else "#ffffff"
    ink = "#d7e2ea" if dark else "#141820"
    muted = "#6b7c8c" if dark else "#64748b"
    edge_dim = "rgba(125,211,199,0.18)" if dark else "rgba(15,118,110,0.18)"

    edge_svg = []
    for a, b in edges:
        x1, y1 = coords[a]
        x2, y2 = coords[b]
        live = status.get(a) == "on" and status.get(b) == "on"
        stroke = "#2dd4bf" if live else edge_dim
        edge_svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="{2 if live else 1.2}" '
            f'stroke-linecap="round"/>'
        )

    node_svg = []
    for name, stt in nodes:
        x, y = coords[name]
        color = STATUS_COLOR.get(stt, "#94a3b8")
        cls = ' class="ac-dot-pending"' if stt == "pending" else ""
        tip = html.escape(STACK_HELP.get(name, name))
        node_svg.append(
            f'<g{cls} style="cursor:help">'
            f'<title>{html.escape(name)} — {stt}&#10;{tip}</title>'
            f'<circle cx="{x}" cy="{y}" r="11" fill="{color}" '
            f'opacity="0.22"/>'
            f'<circle cx="{x}" cy="{y}" r="5.5" fill="{color}" '
            f'stroke="{bg}" stroke-width="2"/>'
            f'<text x="{x}" y="{y + 22}" text-anchor="middle" '
            f'fill="{ink}" font-size="9" '
            f'font-family="IBM Plex Mono, monospace">{html.escape(name)}</text>'
            f"</g>"
        )

    on_n = sum(1 for _, s in nodes if s == "on")
    return f"""<!DOCTYPE html><html><body style="margin:0;background:{bg}">
<svg viewBox="0 0 320 210" width="100%" height="210"
  style="display:block;border-radius:14px;background:{bg}">
  <defs>
    <radialGradient id="g" cx="50%" cy="20%" r="70%">
      <stop offset="0%" stop-color="#1a3a38" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{bg}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="320" height="210" fill="url(#g)"/>
  <text x="12" y="16" fill="{muted}" font-size="9"
    font-family="IBM Plex Mono, monospace" letter-spacing="1.5">CAPABILITY GRAPH</text>
  <text x="308" y="16" fill="{ink}" font-size="9" text-anchor="end"
    font-family="IBM Plex Mono, monospace">{on_n}/{len(nodes)} live</text>
  {''.join(edge_svg)}
  {''.join(node_svg)}
</svg>
<style>@keyframes ac-pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.ac-dot-pending{{animation:ac-pulse 1.4s ease-in-out infinite}}
@media (prefers-reduced-motion:reduce){{.ac-dot-pending{{animation:none}}}}</style>
</body></html>"""


def session_sparkline_html(history: list[dict]) -> str:
    """Latency + token bars from this chat session (hover readout, no OS tooltips)."""
    rows = [h for h in history if h.get("role") == "assistant" and h.get("metrics")]
    if not rows:
        return (
            "<div style='font:11px IBM Plex Mono,monospace;color:#9db0bf;"
            "padding:10px 4px;border:1px dashed rgba(255,255,255,.12);"
            "border-radius:12px'>Run a turn to plot latency & tokens.</div>"
        )
    lat = [float((r.get("metrics") or {}).get("elapsed_s") or 0) for r in rows]
    tok = [int((r.get("metrics") or {}).get("total_tokens") or 0) for r in rows]
    cost = [
        float((r.get("metrics") or {}).get("estimated_cost_usd") or 0) for r in rows
    ]
    w, h = 300, 118
    plot_top, plot_bot = 28, 88
    plot_h = plot_bot - plot_top
    max_lat = max(lat) or 1
    max_tok = max(tok) or 1
    n = len(lat)
    gap = 10
    bw = max(14, (w - 24 - gap * max(n - 1, 0)) / n)
    data = [
        {"i": i + 1, "lat": L, "tok": T, "cost": C}
        for i, (L, T, C) in enumerate(zip(lat, tok, cost))
    ]
    bars = []
    for i, (L, T) in enumerate(zip(lat, tok)):
        x = 12 + i * (bw + gap)
        lh = max(4, (L / max_lat) * plot_h)
        th = max(4, (T / max_tok) * plot_h)
        bars.append(
            f'<g class="bar" data-i="{i}" style="cursor:pointer">'
            f'<rect x="{x}" y="{plot_bot - lh}" width="{bw * 0.42}" height="{lh}" '
            f'rx="3" fill="#2dd4bf"/>'
            f'<rect x="{x + bw * 0.5}" y="{plot_bot - th}" width="{bw * 0.42}" '
            f'height="{th}" rx="3" fill="#f59e0b"/>'
            f'<text x="{x + bw / 2}" y="{plot_bot + 14}" text-anchor="middle" '
            f'fill="#7a8f9e" font-size="9" font-family="IBM Plex Mono,monospace">'
            f"T{i + 1}</text></g>"
        )
    payload = json.dumps(data)
    return f"""<!DOCTYPE html><html><body style="margin:0;background:transparent">
<div style="padding:2px 0 0">
  <div style="display:flex;justify-content:space-between;align-items:center;
    font:10px IBM Plex Mono,monospace;color:#9db0bf;margin-bottom:2px">
    <span>SESSION</span>
    <span><span style="color:#2dd4bf">■</span> latency
      &nbsp;<span style="color:#f59e0b">■</span> tokens</span>
  </div>
  <div id="hint" style="font:11px IBM Plex Mono,monospace;color:#cfe8e3;
    min-height:16px;margin-bottom:2px">Hover a turn</div>
  <svg viewBox="0 0 {w} {h}" width="100%" height="{h}" id="chart">
    <line x1="8" y1="{plot_bot}" x2="{w - 8}" y2="{plot_bot}"
      stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
    {''.join(bars)}
  </svg>
</div>
<script>
(() => {{
  const data = {payload};
  const hint = document.getElementById('hint');
  document.querySelectorAll('.bar').forEach((g) => {{
    g.addEventListener('mouseenter', () => {{
      const d = data[Number(g.dataset.i)];
      if (!d) return;
      hint.textContent = `Turn ${{d.i}} · ${{d.lat.toFixed(1)}}s · ${{d.tok}} tok · $${{d.cost.toFixed(6)}}`;
      g.style.opacity = '1';
      document.querySelectorAll('.bar').forEach((o) => {{
        if (o !== g) o.style.opacity = '0.35';
      }});
    }});
    g.addEventListener('mouseleave', () => {{
      hint.textContent = 'Hover a turn';
      document.querySelectorAll('.bar').forEach((o) => {{ o.style.opacity = '1'; }});
    }});
  }});
}})();
</script>
</body></html>"""


def last_run_card_html(meta: dict) -> str:
    """Compact last-run panel — wraps long demo ids as pills (no caption overflow)."""
    m = meta.get("metrics") or {}
    demo = str(meta.get("demo") or "").strip()
    # Split demo into short chips so long + strings don't blow the sidebar width
    parts = [p for p in re.split(r"[+\s]+", demo) if p] if demo else []
    if not parts and demo:
        parts = [demo[:28] + ("…" if len(demo) > 28 else "")]
    tags = "".join(
        f'<span class="tag">{html.escape(p)}</span>' for p in parts[:8]
    )
    if not tags:
        tags = '<span class="tag">ready</span>'
    elapsed = m.get("elapsed_s", "—")
    toks = m.get("total_tokens", 0)
    cost = m.get("estimated_cost_usd") or 0
    return f"""
<div class="ac-last-run">
  <div class="lbl">Last run</div>
  <div class="metrics">{html.escape(str(elapsed))}s · {html.escape(str(toks))} tok · ${cost:.6f}</div>
  <div class="tags">{tags}</div>
</div>
"""


def activity_feed_html(lines: list[str]) -> str:
    if not lines:
        return (
            "<div style='font:12px IBM Plex Mono,monospace;color:#64748b'>"
            "InvokeAgentRuntime · waiting for first event…</div>"
        )
    items = []
    for line in lines[-16:]:
        # strip markdown-ish backticks for plain feed
        clean = re.sub(r"[*`]", "", line)
        items.append(
            f"<div style='padding:6px 0;border-bottom:1px solid #eef2f6;"
            f"font:12px/1.4 IBM Plex Mono,monospace;color:#334155'>"
            f"{html.escape(clean)}</div>"
        )
    return (
        "<div style='max-height:160px;overflow:auto;padding:2px 4px'>"
        + "".join(items)
        + "</div>"
    )


def render_activity(lines: list[str], box) -> None:
    box.markdown(activity_feed_html(lines), unsafe_allow_html=True)


def filmstrip_html(steps: list[dict], *, autoplay: bool = False) -> str:
    frames = []
    for s in steps or []:
        kind = s.get("kind", "")
        label = html.escape(str(s.get("label") or kind))
        tool = html.escape(str((s.get("tool") or "").split("___")[-1]))
        detail = s.get("input") if kind == "tool_call" else s.get("output")
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)[:260]
        detail = html.escape(str(detail or "")[:260])
        hue = "#0f766e" if kind == "tool_call" else "#b45309"
        frames.append(
            {"title": f"{label}" + (f" · {tool}" if tool else ""), "detail": detail, "hue": hue}
        )
    payload = json.dumps(frames)
    play = "true" if autoplay else "false"
    return f"""<!DOCTYPE html><html><body style="margin:0;font-family:IBM Plex Sans,system-ui,sans-serif">
<div style="border:1px solid #e2e8f0;border-radius:16px;padding:14px;background:
  linear-gradient(160deg,#fff,#f4faf8);box-shadow:0 8px 24px rgba(20,24,32,.04)">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px">
    <div style="font:11px IBM Plex Mono,monospace;letter-spacing:.1em;text-transform:uppercase;color:#64748b">
      Tool timeline
    </div>
    <div style="display:flex;gap:6px">
      <button id="fp" style="background:#0f766e;border:0;color:#fff;border-radius:8px;padding:5px 12px;cursor:pointer;font:12px IBM Plex Sans,sans-serif">Play</button>
      <button id="fs" style="background:#fff;border:1px solid #cbd5e1;border-radius:8px;padding:5px 12px;cursor:pointer;font:12px IBM Plex Sans,sans-serif">Pause</button>
    </div>
  </div>
  <div id="scrub" style="display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap"></div>
  <div id="ft" style="font-size:14px;font-weight:600;min-height:22px;color:#141820">—</div>
  <div id="fd" style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#475569;min-height:48px;white-space:pre-wrap;margin:8px 0;background:#f8fafc;border-radius:10px;padding:10px;border:1px solid #eef2f6"></div>
  <input id="fr" type="range" min="0" max="0" value="0" style="width:100%;accent-color:#0f766e">
</div>
<script>
(() => {{
  const frames = {payload};
  const title = document.getElementById('ft');
  const detail = document.getElementById('fd');
  const range = document.getElementById('fr');
  const scrub = document.getElementById('scrub');
  let i = 0, timer = null;
  if (!frames.length) {{ title.textContent = 'No tool steps this turn'; return; }}
  range.max = String(frames.length - 1);
  frames.forEach((f, idx) => {{
    const d = document.createElement('button');
    d.type = 'button';
    d.title = f.title;
    d.style.cssText = 'width:14px;height:14px;border-radius:4px;border:0;cursor:pointer;background:' + (f.hue || '#94a3b8');
    d.onclick = () => {{ pause(); show(idx); }};
    scrub.appendChild(d);
  }});
  function show(idx) {{
    i = Math.max(0, Math.min(frames.length - 1, idx));
    const f = frames[i];
    title.innerHTML = '<span style="color:' + f.hue + '">●</span> ' + (i + 1) + '/' + frames.length + ' · ' + f.title;
    detail.textContent = f.detail || '';
    range.value = String(i);
    [...scrub.children].forEach((el, j) => {{
      el.style.outline = j === i ? '2px solid #141820' : 'none';
      el.style.opacity = j === i ? '1' : '0.55';
    }});
  }}
  function play() {{
    if (timer) return;
    timer = setInterval(() => {{
      if (i >= frames.length - 1) {{ clearInterval(timer); timer = null; return; }}
      show(i + 1);
    }}, 750);
  }}
  function pause() {{ if (timer) {{ clearInterval(timer); timer = null; }} }}
  document.getElementById('fp').onclick = () => {{ if (i >= frames.length - 1) show(0); play(); }};
  document.getElementById('fs').onclick = pause;
  range.oninput = (e) => {{ pause(); show(Number(e.target.value)); }};
  show(0);
  if ({play}) play();
}})();
</script></body></html>"""


def metrics_strip(metrics: dict) -> None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Latency", f"{metrics.get('elapsed_s', '—')}s")
    m2.metric("Est. cost", f"${metrics.get('estimated_cost_usd') or 0:.6f}")
    m3.metric("Tokens", f"{metrics.get('total_tokens') or 0}")
    m4.metric(
        "In / out",
        f"{metrics.get('prompt_tokens', 0)} / {metrics.get('completion_tokens', 0)}",
    )


def run_chat_turn(prompt: str, *, arn: str, region: str, actor_id: str) -> None:
    """ChatGPT-style turn: user bubble first, then streaming assistant bubble."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    stack = dict(st.session_state.get("last_stack") or {})
    steps_acc: list[dict] = []
    activity: list[str] = []
    final_data: dict[str, Any] | None = None
    streamed = ""
    t0 = time.time()

    with st.chat_message("assistant"):
        with st.expander("Runtime telemetry", expanded=True):
            activity_box = st.empty()
            activity_box.markdown(
                activity_feed_html([]),
                unsafe_allow_html=True,
            )

        def token_generator() -> Iterator[str]:
            nonlocal stack, final_data, streamed
            for evt in stream_research_runtime(
                arn=arn.strip(),
                prompt=prompt.strip(),
                actor_id=(actor_id or "streamlit-user").strip(),
                thread_id=st.session_state.thread_id,
                region=(region or "us-east-1").strip(),
                runtime_session_id=st.session_state.runtime_session_id,
            ):
                kind = evt.get("event")
                elapsed = evt.get("elapsed_s")
                stamp = (
                    f"{elapsed:.1f}s"
                    if isinstance(elapsed, (int, float))
                    else f"{time.time() - t0:.1f}s"
                )

                if kind == "progress":
                    msg = str(evt.get("message") or evt.get("phase") or "progress")
                    activity.append(f"{stamp}  {msg}")
                    render_activity(activity, activity_box)
                    if isinstance(evt.get("stack"), dict):
                        stack = {**evt["stack"], "_probed": True}
                        st.session_state.last_stack = stack

                elif kind == "step":
                    step = evt.get("step") or {}
                    steps_acc.append(step)
                    label = step.get("label") or step.get("kind")
                    tool = str(step.get("tool") or "").split("___")[-1]
                    bit = f"{stamp}  {label}"
                    if tool:
                        bit += f"  [{tool}]"
                    activity.append(bit)
                    render_activity(activity, activity_box)

                elif kind == "token":
                    delta = str(evt.get("delta") or "")
                    if delta:
                        streamed += delta
                        yield delta

                elif kind == "final":
                    final_data = evt
                    if isinstance(evt.get("stack"), dict):
                        stack = {**evt["stack"], "_probed": True}
                        st.session_state.last_stack = stack
                    result = str(evt.get("result") or "")
                    if result and not streamed:
                        streamed = result
                        yield result
                    m = evt.get("metrics") or {}
                    activity.append(
                        f"{stamp}  done · {m.get('total_tokens', 0)} tok · "
                        f"${m.get('estimated_cost_usd') or 0:.6f}"
                    )
                    render_activity(activity, activity_box)

        try:
            written = st.write_stream(token_generator())
            if isinstance(written, str) and written.strip():
                streamed = written
        except Exception as exc:  # noqa: BLE001
            st.error(f"Runtime call failed: `{exc}`")
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"Runtime call failed:\n\n`{exc}`",
                    "steps": [],
                    "stack": stack,
                    "metrics": {"elapsed_s": round(time.time() - t0, 2)},
                    "usage": {},
                }
            )
            return

        if not final_data and not streamed:
            st.warning("Stream ended without a final answer.")
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "Stream ended without a final payload.",
                    "steps": steps_acc,
                    "stack": stack,
                    "metrics": {"elapsed_s": round(time.time() - t0, 2)},
                    "usage": {},
                }
            )
            return

        if final_data and final_data.get("result"):
            streamed = str(final_data["result"])

        metrics = dict((final_data or {}).get("metrics") or {})
        if metrics.get("elapsed_s") is None:
            metrics["elapsed_s"] = round(time.time() - t0, 2)
        usage = (final_data or {}).get("usage") or {}
        steps = (final_data or {}).get("steps") or steps_acc

        metrics_strip(metrics)

        visible_steps = [s for s in steps if s.get("kind") != "assistant"]
        if visible_steps:
            components.html(
                filmstrip_html(visible_steps, autoplay=True),
                height=230,
                scrolling=False,
            )

        on = [n for n, stt in stack_state({**stack, "_probed": True}) if stt == "on"]
        st.caption(
            " · ".join(on)
            + (f" · auth={stack.get('auth_source')}" if stack.get("auth_source") else "")
        )

    st.session_state.last_response_meta = {
        "memory_id": (final_data or {}).get("memory_id"),
        "session_id": (final_data or {}).get("_session_id"),
        "demo": (final_data or {}).get("demo"),
        "metrics": metrics,
        "usage": usage,
        "tools_available": (final_data or {}).get("tools_available") or [],
    }
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": streamed or "(empty)",
            "steps": steps,
            "stack": stack,
            "metrics": metrics,
            "usage": usage,
            "tools_available": (final_data or {}).get("tools_available") or [],
        }
    )
    st.session_state.last_stack = stack


def render_history_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] != "assistant":
            return
        mm = msg.get("metrics") or {}
        if mm:
            metrics_strip(mm)
        steps = [s for s in (msg.get("steps") or []) if s.get("kind") != "assistant"]
        if steps:
            with st.expander("Tool timeline", expanded=False):
                components.html(
                    filmstrip_html(steps, autoplay=False),
                    height=230,
                    scrolling=False,
                )
        s = msg.get("stack") or {}
        on = [n for n, stt in stack_state({**s, "_probed": True}) if stt == "on"]
        if on:
            st.caption(
                " · ".join(on)
                + (f" · auth={s.get('auth_source')}" if s.get("auth_source") else "")
            )


def main() -> None:
    st.set_page_config(
        page_title="AgentCore Research",
        page_icon="⬡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"chat-{uuid.uuid4().hex[:8]}"
    if "runtime_session_id" not in st.session_state:
        st.session_state.runtime_session_id = str(uuid.uuid4())
    if "last_stack" not in st.session_state:
        st.session_state.last_stack = {
            "runtime": True,
            "memory": True,
            "gateway": False,
            "mcp": False,
            "identity": False,
            "rag": True,
            "browser": True,
            "_probed": False,
            "identity_provider": "gateway-cognito-m2m",
            "auth_source": "—",
        }
    if "last_response_meta" not in st.session_state:
        st.session_state.last_response_meta = {}
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None

    arn = os.getenv("RESEARCH_RUNTIME_ARN", DEFAULT_ARN)
    region = os.getenv("AWS_REGION") or _region_from_arn(arn)
    actor_id = "streamlit-user"

    with st.sidebar:
        st.markdown(
            '<div class="ac-side-brand">AgentCore</div>'
            '<div class="ac-side-meta">Research telemetry</div>',
            unsafe_allow_html=True,
        )
        components.html(
            constellation_html(st.session_state.last_stack, dark=True),
            height=220,
            scrolling=False,
        )
        st.caption("Hover nodes for capability notes. Edges light when both ends are live.")

        with st.expander("What each node means", expanded=False):
            for name, text in STACK_HELP.items():
                st.markdown(f"**{name}** — {text}")

        st.markdown("##### Launch prompts")
        for i, sug in enumerate(SUGGESTIONS):
            label = f"{sug['emoji']}  {sug['title']} · {sug['hint']}"
            if st.button(label, key=f"sug_{i}", use_container_width=True):
                st.session_state.pending_prompt = sug["prompt"]
                st.rerun()

        if st.button("New session", type="primary", use_container_width=True):
            st.session_state.messages = []
            st.session_state.thread_id = f"chat-{uuid.uuid4().hex[:8]}"
            st.session_state.runtime_session_id = str(uuid.uuid4())
            st.session_state.pending_prompt = None
            st.session_state.last_response_meta = {}
            st.rerun()

        components.html(
            session_sparkline_html(st.session_state.messages),
            height=140,
            scrolling=False,
        )

        with st.expander("Connection", expanded=False):
            arn = st.text_input("Runtime ARN", value=arn)
            region = st.text_input("Region", value=region)
            actor_id = st.text_input("actor_id", value=actor_id)
            st.text_input("thread_id", value=st.session_state.thread_id, disabled=True)
            sid = st.session_state.runtime_session_id or ""
            st.caption(f"Sticky session · {sid[:8]}…{sid[-6:] if len(sid) > 14 else ''}")

        meta = st.session_state.last_response_meta or {}
        if meta.get("metrics"):
            st.markdown(last_run_card_html(meta), unsafe_allow_html=True)

    # —— Main stage ——
    chips = stack_state(st.session_state.last_stack)
    chip_html = "".join(
        f'<span class="ac-chip"><strong>{html.escape(n)}</strong> · {s}</span>'
        for n, s in chips
    )
    st.markdown(
        f"""
<div class="ac-hero">
  <div>
    <div class="ac-kicker">Bedrock AgentCore · LangGraph</div>
    <h1 class="ac-title">Research desk</h1>
    <p class="ac-sub">
      Token-streamed answers from a StateGraph Runtime — Memory, Gateway MCP,
      Identity, RAG, and cloud Browser as live tools.
    </p>
  </div>
  <div class="ac-chips">{chip_html}</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        cards = "".join(
            f'<div class="ac-card"><div class="sym">{html.escape(s["emoji"])}</div>'
            f'<div class="t">{html.escape(s["title"])}</div>'
            f'<div class="h">{html.escape(s["hint"])}</div></div>'
            for s in SUGGESTIONS
        )
        st.markdown(
            f"""
<div class="ac-empty">
  <h3>Start from a scenario</h3>
  <p style="margin:0;color:#5b6b7c;font-size:0.92rem">
    Pick a launch prompt in the sidebar, or type below. First turn may cold-start
    the Runtime (~10–17s); follow-ups in this session stay warm.
  </p>
  <div class="ac-grid">{cards}</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    for msg in st.session_state.messages:
        render_history_message(msg)

    pending = st.session_state.pending_prompt
    typed = st.chat_input("Ask the research Runtime…")
    prompt = pending or typed
    if pending:
        st.session_state.pending_prompt = None

    if prompt:
        run_chat_turn(prompt, arn=arn, region=region, actor_id=actor_id)
        st.rerun()


if __name__ == "__main__":
    main()
