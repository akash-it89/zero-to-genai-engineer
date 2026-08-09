"""Guardrail options: cross-cutting input/output screening (Req 20).

``light`` (default on) is a local, free, regex/keyword screen — no LLM call, no paid
API. ``Input_Guardrail``: a prompt-injection attempt is blocked with a reason; PII in
the question is flagged (visible to the caller) but not blocked, since it is the
user's own input. ``Output_Guardrail``: PII in the generated answer is flagged and
redacted; unsafe content is blocked with a reason. ``off`` bypasses both screens
entirely — a true identity no-op (Req 20.4).
"""
from __future__ import annotations

import re

from rag.interfaces import Guardrail, GuardrailVerdict

# Common prompt-injection phrasings (Req 20.1, 20.2). Case-insensitive substring/regex match.
_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all )?(the )?(previous|prior|above) instructions",
        r"disregard (the )?(system|previous) prompt",
        r"reveal (your |the )?(system prompt|instructions)",
        r"you are now\b",
        r"act as if you (have no|are not) restrictions",
        r"pretend (you are|to be) (an? )?(unfiltered|unrestricted|jailbroken)",
        r"do anything now",
        r"\bDAN\b",
    ]
]

# Lightweight PII patterns (Req 20.2, 20.3). Not exhaustive — a fast local screen.
_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
}

# Unsafe-content keyword screen for generated output (Req 20.3).
_UNSAFE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bhow to (build|make) a (bomb|explosive|weapon)\b",
        r"\bstep[- ]by[- ]step (instructions )?to (kill|harm|poison)\b",
        r"\bsynthesiz(e|ing) (a )?(nerve agent|chemical weapon)\b",
    ]
]


def _find_pii(text: str) -> list[str]:
    return [name for name, pattern in _PII_PATTERNS.items() if pattern.search(text)]


def _redact_pii(text: str) -> str:
    redacted = text
    for pattern in _PII_PATTERNS.values():
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class OffGuardrail(Guardrail):
    """Disabled: both screens are true identity no-ops (Req 20.4)."""

    def screen_input(self, question: str) -> GuardrailVerdict:
        return GuardrailVerdict(allowed=True, flagged=False, reason="", text=question)

    def screen_output(self, answer: str) -> GuardrailVerdict:
        return GuardrailVerdict(allowed=True, flagged=False, reason="", text=answer)


class LightGuardrail(Guardrail):
    """Default-on local regex/keyword input+output screen (Req 20.1-20.3, 20.5)."""

    def screen_input(self, question: str) -> GuardrailVerdict:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(question):
                return GuardrailVerdict(
                    allowed=False,
                    flagged=True,
                    reason=f"prompt-injection pattern detected: '{pattern.pattern}'",
                    text=question,
                )
        pii_found = _find_pii(question)
        if pii_found:
            return GuardrailVerdict(
                allowed=True,
                flagged=True,
                reason=f"PII detected in question: {', '.join(pii_found)}",
                text=question,
            )
        return GuardrailVerdict(allowed=True, flagged=False, reason="", text=question)

    def screen_output(self, answer: str) -> GuardrailVerdict:
        for pattern in _UNSAFE_PATTERNS:
            if pattern.search(answer):
                return GuardrailVerdict(
                    allowed=False,
                    flagged=True,
                    reason=f"unsafe content pattern detected: '{pattern.pattern}'",
                    text="",
                )
        pii_found = _find_pii(answer)
        if pii_found:
            return GuardrailVerdict(
                allowed=True,
                flagged=True,
                reason=f"PII redacted from answer: {', '.join(pii_found)}",
                text=_redact_pii(answer),
            )
        return GuardrailVerdict(allowed=True, flagged=False, reason="", text=answer)


def make_guardrail(name: str) -> Guardrail:
    """Construct the Guardrail registered under ``name`` (Req 1.1, 20)."""
    if name == "off":
        return OffGuardrail()
    if name == "light":
        return LightGuardrail()
    raise ValueError(f"Unknown guardrail option: '{name}'")
