from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from agentic_scd.api.app import create_app
from agentic_scd.config import Settings, get_settings
from agentic_scd.data.history import baseline_from_history
from agentic_scd.graph import build_graph
from agentic_scd.ingestion.batch_cli import run as run_batch
from agentic_scd.ingestion.schema import DisruptionSignal, Location
from agentic_scd.mcp.external_data import ExternalDataMCP


def make_signal(title: str, body: str, region: str, hint: str = "high") -> DisruptionSignal:
    return DisruptionSignal(
        signal_id=title.lower().replace(" ", "-"),
        source="test",
        source_type="WEBHOOK",
        source_reliability=0.9,
        fetched_at=datetime.now(UTC),
        title=title,
        raw_text=body,
        location=Location(region=region),
        severity_hint=hint,
    )


def test_graph_high_severity_runs_full_pipeline() -> None:
    graph = build_graph()
    state = graph.invoke(
        {
            "new_signals": [
                make_signal(
                    "Typhoon closes Shanghai port",
                    "Typhoon flooding and shipping delays are disrupting the Shanghai port and carrier schedules.",
                    "China",
                    "severe",
                )
            ]
        }
    )
    # HIGH severity no longer shortcuts — every signal runs the full pipeline.
    assert state["classifications"][0].risk_level == "HIGH"
    assert state["classifications"][0].route == "full_path"
    assert state.get("impacts")
    assert state.get("forecast") is not None
    assert state["simulation"].stockout_probability >= 0
    assert state["recommendation"].actions


def test_baseline_from_history_prefers_database(tmp_path) -> None:
    cfg = Settings(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path / 'test.sqlite'}")
    batch, _ = run_batch(cfg, do_load=True, do_retain=False)
    baseline, source = baseline_from_history(8, cfg)
    assert batch is not None
    assert batch.totals.loaded >= 1
    assert source == "database"
    assert len(baseline) == 8


def test_api_run_uses_pending_signals_and_health_reports_modes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_SCD_HOME", str(tmp_path))
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["database_mode"] == "sqlite"
    assert health_payload["llm_mode"] == "mock"
    posted = client.post(
        "/signals",
        json={
            "title": "Port strike delays Rotterdam shipments",
            "body": "Port strike and shipping congestion are delaying containers moving through Rotterdam.",
            "location": {"region": "Netherlands"},
            "payload": {"severity_hint": "moderate"},
        },
    )
    assert posted.status_code == 200
    response = client.post("/run", json={"use_pending_signals": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["new_signals"]
    assert payload["new_signals"][0]["title"].startswith("Port strike")
    assert payload["recommendation"]["actions"]


def test_mcp_runtime_tools_are_available(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_SCD_HOME", str(tmp_path))
    get_settings.cache_clear()
    mcp = ExternalDataMCP()
    names = {tool["name"] for tool in mcp.list_tools()}
    assert "inspect_runtime_state" in names
    assert "load_network_knowledge" in names
    runtime = mcp.call_tool("inspect_runtime_state", {"signal_limit": 1, "run_limit": 1})
    assert runtime["database_mode"] == "sqlite"
    assert "recent_signals" in runtime
