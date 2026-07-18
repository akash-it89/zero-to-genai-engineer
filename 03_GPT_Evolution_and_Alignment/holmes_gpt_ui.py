"""
Holmes GPT — Streamlit UI
Stream text one token at a time from the GPT trained on Sherlock Holmes.
Run: streamlit run holmes_gpt_ui.py
"""

import math
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
import streamlit as st
import torch
import torch.nn.functional as F
from torch import nn

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Holmes GPT",
    page_icon="🔍",
    layout="wide",
)

# ── Paths / device ─────────────────────────────────────────────────────────────
_DIR       = os.path.dirname(os.path.abspath(__file__))
CKPT_PATH  = os.path.join(_DIR, "notebooks", "gpt_holmes.pt")
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

HOLMES_URLS = [
    "https://www.gutenberg.org/files/1661/1661-0.txt",
    "https://gutenberg.org/cache/epub/1661/pg1661.txt",
]

# ══════════════════════════════════════════════════════════════════════════════
#  MODEL ARCHITECTURE  — must be byte-for-byte identical to the training notebook
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GPTConfig:
    vocab_size : int   = 65
    block_size : int   = 128
    n_embd     : int   = 128
    n_heads    : int   = 4
    n_layers   : int   = 4
    dropout    : float = 0.1


class CausalSelfAttention(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        assert config.n_embd % config.n_heads == 0
        self.n_heads   = config.n_heads
        self.n_embd    = config.n_embd
        self.head_size = config.n_embd // config.n_heads
        self.c_attn    = nn.Linear(config.n_embd, 3 * config.n_embd, bias=False)
        self.c_proj    = nn.Linear(config.n_embd, config.n_embd, bias=False)
        self.attn_drop = nn.Dropout(config.dropout)
        self.resid_drop= nn.Dropout(config.dropout)
        self.register_buffer(
            "mask",
            torch.tril(torch.ones(config.block_size, config.block_size))
                  .view(1, 1, config.block_size, config.block_size),
        )

    def forward(self, x: torch.Tensor):
        B, T, C = x.shape
        q, k, v = self.c_attn(x).split(self.n_embd, dim=2)

        def split_heads(t):
            return t.view(B, T, self.n_heads, self.head_size).transpose(1, 2)

        q, k, v = split_heads(q), split_heads(k), split_heads(v)
        scale   = 1.0 / math.sqrt(self.head_size)
        att     = (q @ k.transpose(-2, -1)) * scale
        att     = att.masked_fill(self.mask[:, :, :T, :T] == 0, float("-inf"))
        att     = F.softmax(att, dim=-1)
        att     = self.attn_drop(att)
        out     = att @ v
        out     = out.transpose(1, 2).contiguous().view(B, T, C)
        out     = self.resid_drop(self.c_proj(out))
        return out, att


class FeedForward(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(config.n_embd, 4 * config.n_embd, bias=False),
            nn.GELU(),
            nn.Linear(4 * config.n_embd, config.n_embd, bias=False),
            nn.Dropout(config.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.ln1  = nn.LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config)
        self.ln2  = nn.LayerNorm(config.n_embd)
        self.ff   = FeedForward(config)

    def forward(self, x: torch.Tensor):
        attn_out, attn_w = self.attn(self.ln1(x))
        x = x + attn_out
        x = x + self.ff(self.ln2(x))
        return x, attn_w


class GPT(nn.Module):
    def __init__(self, config: GPTConfig):
        super().__init__()
        self.config  = config
        self.wte     = nn.Embedding(config.vocab_size, config.n_embd)
        self.wpe     = nn.Embedding(config.block_size, config.n_embd)
        self.drop    = nn.Dropout(config.dropout)
        self.blocks  = nn.ModuleList([TransformerBlock(config) for _ in range(config.n_layers)])
        self.ln_f    = nn.LayerNorm(config.n_embd)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def forward(self, idx: torch.Tensor, targets=None):
        B, T = idx.shape
        pos  = torch.arange(T, dtype=torch.long, device=idx.device)
        x    = self.drop(self.wte(idx) + self.wpe(pos))
        for block in self.blocks:
            x, _ = block(x)
        x      = self.ln_f(x)
        logits = self.lm_head(x)
        loss   = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss


# ══════════════════════════════════════════════════════════════════════════════
#  TOKENIZER  — same WordTokenizer logic as the training notebook
# ══════════════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[A-Za-z']+|[^A-Za-z'\s]|\n")


class WordTokenizer:
    """
    Word-level tokenizer — rebuilt from the same Holmes corpus used for training.
    Vocabulary is deterministic: sorted unique tokens from the text.
    """

    def __init__(self, text: str):
        tokens           = _WORD_RE.findall(text)
        vocab            = sorted(set(tokens))
        self.vocab_size  = len(vocab)
        self.word_to_idx = {w: i for i, w in enumerate(vocab)}
        self.idx_to_word = {i: w for i, w in enumerate(vocab)}

    def encode(self, text: str) -> list:
        return [self.word_to_idx[t] for t in _WORD_RE.findall(text) if t in self.word_to_idx]

    def decode_one(self, token_id: int, prev_token: Optional[str]) -> str:
        """Return the string piece to append for a single generated token."""
        tok = self.idx_to_word[token_id]
        if prev_token is None:
            return tok
        if tok == "\n":
            return "\n"
        if prev_token == "\n":
            return tok
        # Word tokens get a leading space; punctuation attaches directly
        return (" " + tok) if re.match(r"[A-Za-z']", tok) else tok


# ══════════════════════════════════════════════════════════════════════════════
#  CACHED LOADERS  — run once per Streamlit server process
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="📚 Downloading Holmes corpus & rebuilding vocabulary…")
def load_tokenizer() -> WordTokenizer:
    for url in HOLMES_URLS:
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                return WordTokenizer(r.text)
        except Exception:
            continue
    st.error("Could not download the Holmes corpus. Check your internet connection.")
    st.stop()


@st.cache_resource(show_spinner="🧠 Loading GPT model weights…")
def load_model() -> GPT:
    if not os.path.exists(CKPT_PATH):
        st.error(f"Checkpoint not found: {CKPT_PATH}")
        st.stop()
    ckpt   = torch.load(CKPT_PATH, map_location=DEVICE, weights_only=False)
    config = GPTConfig(**ckpt["config"])
    model  = GPT(config).to(DEVICE)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMING GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def token_stream(
    model: GPT,
    tokenizer: WordTokenizer,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_k: int,
):
    """
    Yield one text piece per generated token — the same autoregressive loop
    that runs in the training notebook, adapted for real-time streaming.
    """
    ids = tokenizer.encode(prompt)
    if not ids:
        yield "*(prompt contained no tokens known to this vocabulary)*"
        return

    context  = torch.tensor(ids, dtype=torch.long, device=DEVICE).unsqueeze(0)
    prev_tok = tokenizer.idx_to_word.get(ids[-1])   # last token of prompt

    model.eval()
    with torch.no_grad():
        for _ in range(max_new_tokens):
            # Crop context to the model's maximum block size
            ctx = context[:, -model.config.block_size:]

            logits, _ = model(ctx)
            next_logits = logits[0, -1, :] / temperature   # (vocab_size,)

            # Top-K: keep only the k most-likely candidates
            v, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
            next_logits[next_logits < v[-1]] = float("-inf")

            probs       = F.softmax(next_logits, dim=-1)
            next_id     = torch.multinomial(probs.unsqueeze(0), 1)     # (1, 1)
            next_id_val = next_id.item()

            # Decode this single token with correct word-boundary spacing
            piece    = tokenizer.decode_one(next_id_val, prev_tok)
            prev_tok = tokenizer.idx_to_word[next_id_val]

            context  = torch.cat([context, next_id], dim=1)

            yield piece
            time.sleep(0.03)   # pacing — remove for maximum speed


# ══════════════════════════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    tokenizer = load_tokenizer()
    model     = load_model()

    n_params = sum(p.numel() for p in model.parameters())

    # ── Custom CSS ─────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
        .output-box {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 1.2rem 1.5rem;
            font-family: "Georgia", serif;
            font-size: 1.05rem;
            line-height: 1.75;
            color: #e2e8f0;
            min-height: 120px;
        }
        .prompt-label { color: #94a3b8; font-size: 0.85rem; margin-bottom: 4px; }
    </style>
    """, unsafe_allow_html=True)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("⚙️ Generation Controls")
        st.caption(
            f"Vocab: **{model.config.vocab_size:,}** tokens · "
            f"Params: **{n_params/1e6:.1f}M** · "
            f"Device: **{DEVICE.upper()}**"
        )
        st.divider()

        temperature = st.slider(
            "Temperature",
            min_value=0.1, max_value=2.0, value=0.8, step=0.05,
            help="Higher → more creative / random. Lower → more repetitive / focused.",
        )
        top_k = st.slider(
            "Top-K",
            min_value=1, max_value=100, value=40,
            help="Only sample from the top-K most likely next tokens at each step.",
        )
        max_tokens = st.slider(
            "Max new tokens",
            min_value=25, max_value=500, value=150, step=25,
            help="How many new tokens to generate after your prompt.",
        )

        st.divider()
        st.markdown("**Example prompts**")
        examples = [
            "Holmes had been sitting in silence",
            "My dear Watson, the evidence clearly",
            "The game is afoot. I had",
            "It was a cold evening when",
            "I confess that I was",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True, key=f"ex_{ex[:10]}"):
                st.session_state["prompt"] = ex

    # ── Main panel ─────────────────────────────────────────────────────────────
    st.title("🔍 Holmes GPT")
    st.caption(
        "Mini GPT trained from scratch on *The Adventures of Sherlock Holmes* · "
        "Streams one token at a time — just like ChatGPT under the hood."
    )
    st.divider()

    prompt = st.text_area(
        "Your prompt",
        value=st.session_state.get("prompt", "Holmes said"),
        height=90,
        placeholder="Type a Holmes-style opening line…",
    )

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        generate = st.button("▶  Generate", type="primary", use_container_width=True)
    with col_info:
        st.caption(f"temperature={temperature} · top_k={top_k} · max_tokens={max_tokens}")

    st.divider()

    if generate:
        if not prompt.strip():
            st.warning("Please enter a prompt first.")
            return

        st.markdown(f'<p class="prompt-label">PROMPT</p>', unsafe_allow_html=True)
        st.info(prompt.strip(), icon="💬")

        st.markdown(f'<p class="prompt-label">GENERATED CONTINUATION</p>', unsafe_allow_html=True)

        # st.write_stream accepts any generator that yields strings.
        # It renders each piece as it arrives — the ChatGPT-style effect.
        gen = token_stream(
            model, tokenizer,
            prompt.strip(),
            max_tokens, temperature, top_k,
        )
        st.write_stream(gen)


if __name__ == "__main__":
    main()
