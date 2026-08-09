"""Feature: rag-studio — config-store and variant-integrity property tests.

Covers P7 (omitted fields get documented defaults), P8 (variant serialization
round-trip across a simulated restart), P23 (duplicate-name save rejected, store
unchanged; delete removes exactly one and retains others), and P17 (variant failure
isolation: results + errors count == variant count). Req 2.2, 2.4, 2.5, 2.7, 6.4,
14.2, 22.2, 23.3.
"""
from __future__ import annotations

import contextlib
import shutil
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from rag.config import PipelineConfig
from rag.interfaces import AnswerResult, Principal
from rag.persistence import DuplicateVariantNameError, SqlitePersistence
from rag.pipeline import RagStudioPipeline

names = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=8)


@contextlib.contextmanager
def _tmp_dir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# P7 — omitted fields get documented defaults (Req 2.5, 2.7, 22.2)
# ---------------------------------------------------------------------------

@given(name=names, top_k=st.integers(min_value=1, max_value=50))
@settings(max_examples=100)
def test_p7_normalize_fills_documented_defaults_for_omitted_fields(name, top_k):
    partial = {"name": name, "top_k": top_k}   # everything else omitted
    config = PipelineConfig.normalize(partial)

    assert config.name == name
    assert config.top_k == top_k
    # Documented defaults (Req 2.5) for every omitted field.
    assert config.query_transform == "none"
    assert config.post_retrieval == "none"
    assert config.orchestrator == "linear"
    assert config.caching == "exact_match"
    assert config.guardrails == "light"
    assert config.temperature == 0.0


@given(name=names)
@settings(max_examples=50)
def test_p7_normalize_preserves_supplied_values(name):
    partial = {"name": name, "query_transform": "hyde", "guardrails": "off"}
    config = PipelineConfig.normalize(partial)
    assert config.query_transform == "hyde"
    assert config.guardrails == "off"


# ---------------------------------------------------------------------------
# P8 — variant serialization round-trip across a simulated restart (Req 2.4)
# ---------------------------------------------------------------------------

@given(name=names, chunk_size=st.integers(min_value=100, max_value=2000))
@settings(max_examples=30, deadline=None)
def test_p8_variant_round_trips_across_simulated_restart(name, chunk_size):
    with _tmp_dir() as tmp:
        db_path = f"{tmp}/rag_studio.sqlite"
        store1 = SqlitePersistence(db_path=db_path, upload_dir=f"{tmp}/uploads")
        config = PipelineConfig(name=name, chunk_size=chunk_size)
        store1.save_variant(config.name, config.to_dict())
        store1.close()

        # Simulate a restart: a brand-new connection to the same db file.
        store2 = SqlitePersistence(db_path=db_path, upload_dir=f"{tmp}/uploads")
        reloaded = PipelineConfig.from_dict(store2.get_variant(name))
        store2.close()

    assert reloaded.name == config.name
    assert reloaded.chunk_size == config.chunk_size
    assert reloaded == config


# ---------------------------------------------------------------------------
# P23 — duplicate-name save rejected (store unchanged); delete removes exactly one
# ---------------------------------------------------------------------------

@given(name=names, other_names=st.lists(names, min_size=1, max_size=4, unique=True))
@settings(max_examples=50, deadline=None)
def test_p23_duplicate_name_rejected_store_unchanged(name, other_names):
    with _tmp_dir() as tmp:
        store = SqlitePersistence(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")
        original = PipelineConfig(name=name, top_k=7)
        store.save_variant(original.name, original.to_dict())

        duplicate = PipelineConfig(name=name, top_k=999)   # different config, same name
        try:
            store.save_variant(duplicate.name, duplicate.to_dict())
            raised = None
        except DuplicateVariantNameError as exc:
            raised = exc

        assert raised is not None
        # Store unchanged: the original config, not the rejected duplicate's.
        assert store.get_variant(name)["top_k"] == 7
        store.close()


@given(name=names, other_names=st.lists(names, min_size=1, max_size=4, unique=True))
@settings(max_examples=50, deadline=None)
def test_p23_delete_removes_exactly_one_retains_others(name, other_names):
    if name in other_names:
        return
    with _tmp_dir() as tmp:
        store = SqlitePersistence(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")
        all_names = [name, *other_names]
        for n in all_names:
            store.save_variant(n, PipelineConfig(name=n).to_dict())

        store.delete_variant(name)

        remaining = store.list_variants()
        assert name not in remaining
        assert set(remaining.keys()) == set(other_names)
        store.close()


# ---------------------------------------------------------------------------
# P17 — variant failure isolation: results + errors count == variant count
# ---------------------------------------------------------------------------

@given(
    outcomes=st.lists(st.booleans(), min_size=0, max_size=8),   # True = succeeds, False = raises
)
@settings(max_examples=100, deadline=None)
def test_p17_variant_failure_isolation(outcomes):
    with _tmp_dir() as tmp:
        pipeline = RagStudioPipeline(db_path=f"{tmp}/db.sqlite", upload_dir=f"{tmp}/uploads")
        configs = [PipelineConfig(name=f"v{i}") for i in range(len(outcomes))]

        def fake_run_variant(config, question, principal):
            idx = int(config.name[1:])
            if outcomes[idx]:
                return AnswerResult(variant_name=config.name, answer="ok")
            raise RuntimeError(f"{config.name} exploded")

        pipeline.run_variant = fake_run_variant  # plain attribute override, no fixture

        outcome = pipeline.run_all_variants(configs, "question?", Principal(id="u1"))

        assert len(outcome.results) + len(outcome.errors) == len(configs)
        for i, succeeded in enumerate(outcomes):
            name = f"v{i}"
            if succeeded:
                assert name in outcome.results
                assert name not in outcome.errors
            else:
                assert name in outcome.errors
                assert name not in outcome.results
