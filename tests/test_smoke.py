"""Phase 0 smoke test: the package imports, the graph runs offline, and the
returned state carries ``new_signals`` of ``DisruptionSignal``."""

import agentic_scd
from agentic_scd.__main__ import run
from agentic_scd.config.settings import Settings
from agentic_scd.ingestion.schema import SCHEMA_VERSION, DisruptionSignal
from agentic_scd.llm import completion


def test_package_imports() -> None:
    assert agentic_scd.__version__


def test_graph_run_emits_signals() -> None:
    state = run()
    assert "new_signals" in state
    signals = state["new_signals"]
    assert isinstance(signals, list)
    assert len(signals) >= 1
    assert all(isinstance(s, DisruptionSignal) for s in signals)
    assert all(s.schema_version == SCHEMA_VERSION for s in signals)
    # Phase 3/4 fields are nullable and unset at ingestion.
    assert all(s.category is None and s.affected_entities is None for s in signals)


def test_llm_mock_offline() -> None:
    # Force mock mode via explicit settings so the test is hermetic: no network
    # call and no dependence on whether a GROQ_API_KEY is configured in .env.
    mock_settings = Settings(groq_api_key=None, groq_model="unused", use_mock_llm=True)
    first = completion("hello supply chain", settings=mock_settings)
    second = completion("hello supply chain", settings=mock_settings)
    assert first.startswith("[MOCK-LLM:")
    assert first == second
