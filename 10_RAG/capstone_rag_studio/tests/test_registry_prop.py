"""Feature: rag-studio — registry / options-catalog property tests.

Covers design properties P4, P5, P6, P9 (Req 1.2, 1.3, 1.5, 1.7, 2.6, 4.8, 9.3,
9.4, 9.5, 12.4, 12.5, 16.6, 21.5, 21.6).
"""
from __future__ import annotations

import contextlib
import copy
import os

from hypothesis import given, settings
from hypothesis import strategies as st

from rag import registry as R
from rag.config import PipelineConfig

ALL_ENV_KEYS = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY", "PINECONE_API_KEY"]


@contextlib.contextmanager
def env_only(present):
    """Set exactly `present` Env_Keys, restore the prior environment afterwards.

    Used instead of the monkeypatch fixture because Hypothesis re-runs the test body
    many times per invocation and function-scoped fixtures are not reset between runs.
    """
    present = set(present)
    saved = {k: os.environ.get(k) for k in ALL_ENV_KEYS}
    try:
        for k in ALL_ENV_KEYS:
            if k in present:
                os.environ[k] = "test-value"
            else:
                os.environ.pop(k, None)
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --- P4: availability annotation is exactly key-presence -------------------
@settings(max_examples=100)
@given(present=st.lists(st.sampled_from(ALL_ENV_KEYS), unique=True))
def test_p4_availability_equals_key_presence(present):
    # Feature: rag-studio, Property 4: availability == (needs is None or needs present);
    # every reserved option is available==false and annotated reserved.
    with env_only(present):
        snap = R.options_snapshot()
        for category, options in snap.items():
            for key, view in options.items():
                opt = R.get_option(category, key)
                if opt.reserved:
                    assert view["available"] is False
                    assert view["reserved"] is True
                    assert view["reserved_target"] is not None
                else:
                    expected = opt.needs is None or opt.needs in set(present)
                    assert view["available"] is expected
                # secrets never leak: only key NAMES appear
                assert view["requires_key"] in (None, *ALL_ENV_KEYS)


# --- P5: unavailable/reserved selections rejected with a descriptive cause ---
def test_p5_missing_key_rejected_naming_key():
    # Feature: rag-studio, Property 5 (missing key): error names the exact Env_Key.
    with env_only(set()):  # no keys
        cfg = PipelineConfig(reranker="cohere")   # needs COHERE_API_KEY
        errors = R.validate_config(cfg)
    assert any("COHERE_API_KEY" in e for e in errors)


def test_p5_reserved_selection_rejected():
    # Feature: rag-studio, Property 5 (reserved): error states reserved slot unavailable in v1.
    with env_only(set(ALL_ENV_KEYS)):
        cfg = PipelineConfig(query_transform="query_decomposition")
        errors = R.validate_config(cfg)
    assert any("reserved extension slot" in e.lower() for e in errors)


# --- P6: plug-and-play additivity ------------------------------------------
@settings(max_examples=100)
@given(
    category=st.sampled_from(sorted(R.REGISTRY.keys())),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=4, max_size=10),
)
def test_p6_additivity(category, suffix):
    # Feature: rag-studio, Property 6: registering one option yields catalog = old + one,
    # every pre-existing entry byte-for-byte unchanged.
    before = copy.deepcopy(R.options_snapshot())
    new_key = f"synthetic_{suffix}"
    if new_key in R.REGISTRY.get(category, {}):
        return
    try:
        R.register_option(category, R.Option(new_key, "Synthetic", "Retriever", is_local=True))
        after = R.options_snapshot()
        # exactly one new key in this category, all others identical
        assert set(after[category]) == set(before[category]) | {new_key}
        for cat, opts in before.items():
            for key, view in opts.items():
                assert after[cat][key] == view  # unchanged
    finally:
        R.REGISTRY[category].pop(new_key, None)


# --- P9: config validated against the registry -----------------------------
def _valid_config_strategy():
    """Draw a config whose every registry-backed field is a real, non-reserved key."""
    choices = {}
    for field_name, category in R.FIELD_TO_CATEGORY.items():
        keys = [k for k, o in R.REGISTRY[category].items() if not o.reserved]
        choices[field_name] = st.sampled_from(sorted(keys))
    return st.fixed_dictionaries(choices)


@settings(max_examples=100)
@given(fields=_valid_config_strategy())
def test_p9_valid_config_passes(fields):
    # Feature: rag-studio, Property 9 (positive): every-field-registered config validates.
    with env_only(set(ALL_ENV_KEYS)):  # all keys present -> availability satisfied
        cfg = PipelineConfig.normalize(fields)
        assert R.validate_config(cfg) == []


@settings(max_examples=100)
@given(
    field_name=st.sampled_from(sorted(R.FIELD_TO_CATEGORY.keys())),
    bad=st.text(min_size=1, max_size=12).filter(lambda s: "/" not in s),
)
def test_p9_unregistered_value_rejected(field_name, bad):
    # Feature: rag-studio, Property 9 (negative): an unregistered field value is rejected,
    # and the error identifies the offending field.
    category = R.FIELD_TO_CATEGORY[field_name]
    if R.get_option(category, bad) is not None:
        return
    with env_only(set(ALL_ENV_KEYS)):
        cfg = PipelineConfig.normalize({field_name: bad})
        errors = R.validate_config(cfg)
    assert any(field_name in e for e in errors)
