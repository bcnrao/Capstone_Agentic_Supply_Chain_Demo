from __future__ import annotations

from fastapi.testclient import TestClient

from agentic_scd.api.app import create_app


def test_api_run_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_SCD_HOME", str(tmp_path))
    client = TestClient(create_app())
    response = client.post("/run", json={"scenario_name": "Supplier quality failure"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["classifications"]
    assert payload["recommendation"]["actions"]


def test_api_what_if_endpoint(tmp_path, monkeypatch):
    """The what-if endpoint re-simulates from a run's serialized state + overrides.
    Exercises nested Classification/ImpactMap/Forecast round-tripping through JSON."""
    monkeypatch.setenv("AGENTIC_SCD_HOME", str(tmp_path))
    client = TestClient(create_app())
    run = client.post("/run", json={"scenario_name": "Supplier quality failure"}).json()

    body = {
        "classifications": run["classifications"],
        "impacts": run["impacts"],
        "forecast": run.get("forecast"),
        "overrides": {"risk": 0.9, "inventory_multiplier": 0.5, "iterations": 100},
    }
    response = client.post("/simulate/what-if", json=body)
    assert response.status_code == 200
    sim = response.json()
    assert sim["iterations"] == 100
    assert sim["params"]["risk"] == 0.9
    assert 0.0 <= sim["stockout_probability"] <= 1.0
    assert "revenue_histogram" in sim


def test_api_what_if_rejects_out_of_range(tmp_path, monkeypatch):
    """Server-side range validation guards the sync handler from a self-DoS."""
    monkeypatch.setenv("AGENTIC_SCD_HOME", str(tmp_path))
    client = TestClient(create_app())
    response = client.post(
        "/simulate/what-if",
        json={"classifications": [], "impacts": [], "overrides": {"iterations": 99999}},
    )
    assert response.status_code == 422
