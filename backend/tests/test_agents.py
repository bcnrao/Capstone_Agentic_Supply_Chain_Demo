"""Per-stub agent nodes — deterministic typed outputs, fully offline."""

from datetime import UTC, datetime

import agentic_scd.agents.classify as classify_module
from agentic_scd.agents.classify import classify_node, classify_signal
from agentic_scd.agents.forecast import HORIZON, aggregate_risk, forecast_node
from agentic_scd.agents.impact import impact_node
from agentic_scd.agents.recommend import recommend_node
from agentic_scd.agents.schema import (
    Classification,
    Forecast,
    ImpactMap,
    Recommendation,
    Simulation,
)
from agentic_scd.agents.simulate import simulate_node
from agentic_scd.ingestion.schema import DisruptionSignal


def make_signal(
    title: str, body: str = "", reliability: float = 0.8
) -> DisruptionSignal:
    return DisruptionSignal(
        signal_id="sig-1",
        source="stub",
        source_type="RSS",
        source_reliability=reliability,
        fetched_at=datetime.now(UTC),
        title=title,
        raw_text=body,
    )


def test_classify_assigns_category_and_bounded_score() -> None:
    c = classify_signal(make_signal("Port strike halts shipments", "freight delay"))
    assert isinstance(c, Classification)
    assert c.category in {"labor", "logistics"}  # both present; best-match wins
    assert 0.0 <= c.risk_score <= 1.0
    assert c.rationale


def test_classify_off_topic_is_other_low_score() -> None:
    c = classify_signal(make_signal("Bakery wins dessert award"))
    assert c.category == "other"
    assert c.risk_score <= 0.5


def test_classify_node_over_batch() -> None:
    state = {"new_signals": [make_signal("Tariff embargo on imports")]}
    out = classify_node(state)
    assert len(out["classifications"]) == 1
    assert out["classifications"][0].category == "policy"


def test_impact_node_maps_to_network() -> None:
    signal = make_signal("Typhoon hits Shanghai port", "shipping disrupted at the Shanghai hub")
    state = {
        "new_signals": [signal],
        "classifications": [Classification(signal_id="sig-1", category="weather", risk_score=0.9)],
    }
    impacts = impact_node(state)["impacts"]
    assert len(impacts) == 1 and isinstance(impacts[0], ImpactMap)
    # Shanghai grounds to Supplier A + the Shanghai-Los Angeles lane, with products.
    assert impacts[0].affected_suppliers
    assert "Shanghai-Los Angeles" in impacts[0].affected_lanes
    assert impacts[0].product_categories  # products now populate (was the bug)


def test_impact_node_no_material_impact() -> None:
    signal = make_signal(
        "Australian iron ore miners strike at Port Hedland",
        "iron ore export halt in Western Australia",
    )
    state = {
        "new_signals": [signal],
        "classifications": [Classification(signal_id="sig-1", category="labor_strike", risk_score=0.85)],
    }
    impacts = impact_node(state)["impacts"]
    assert len(impacts) == 1
    assert impacts[0].affected_entities == []  # nothing in our network is exposed


def test_forecast_bends_under_material_impact() -> None:
    classifications = [Classification(signal_id="x", category="labor", risk_score=0.8)]
    impacts = [ImpactMap(signal_id="x", affected_suppliers=["Supplier A"], affected_lanes=["Shanghai-Los Angeles"])]
    f: Forecast = forecast_node({"classifications": classifications, "impacts": impacts})["forecast"]
    assert len(f.baseline) == HORIZON and len(f.adjusted) == HORIZON
    assert f.adjusted[-1] < f.baseline[-1]  # demand dips under a material impact
    # No material impact -> flat, even at nonzero risk.
    flat = forecast_node({"classifications": classifications, "impacts": []})["forecast"]
    assert flat.adjusted == flat.baseline


def test_aggregate_risk_mean() -> None:
    cs = [
        Classification(signal_id="a", category="labor", risk_score=0.4),
        Classification(signal_id="b", category="policy", risk_score=0.6),
    ]
    assert aggregate_risk(cs) == 0.5
    assert aggregate_risk([]) == 0.0


def test_simulate_bounds_and_scaling() -> None:
    classifications = [Classification(signal_id="x", category="labor", risk_score=0.5)]
    impacts = [ImpactMap(signal_id="x", affected_entities=["a", "b", "c"])]
    sim: Simulation = simulate_node(
        {"classifications": classifications, "impacts": impacts}
    )["simulation"]
    assert 0.0 <= sim.stockout_probability <= 1.0
    assert sim.revenue_impact > 0.0
    # No risk -> no impact.
    zero = simulate_node({"classifications": [], "impacts": []})["simulation"]
    assert zero.stockout_probability == 0.0
    assert zero.revenue_impact == 0.0


def test_recommend_produces_actions() -> None:
    state = {
        "classifications": [
            Classification(signal_id="x", category="logistics", risk_score=0.7)
        ],
        "impacts": [ImpactMap(signal_id="x", affected_entities=["Port of Rotterdam"])],
        "simulation": Simulation(stockout_probability=0.5, revenue_impact=100.0),
    }
    rec: Recommendation = recommend_node(state)["recommendation"]
    assert len(rec.actions) >= 1
    # The LLM may generate non-freight wording; check that logistics-relevant
    # content appears somewhere in the full action set or structured actions.
    all_text = " ".join(rec.actions).lower()
    structured_text = " ".join(a.action for a in rec.structured_actions).lower() if rec.structured_actions else ""
    assert any(word in all_text or word in structured_text
               for word in ("freight", "logistics", "port", "carrier", "shipment", "rotterdam"))
    assert rec.summary


def test_selects_distilbert_when_confidence_is_low(monkeypatch: object) -> None:
    signal = make_signal("Port strike disrupts shipping", "freight delay")

    def fake_predict(text: str) -> tuple[str, float]:
        assert text == signal.text
        return "logistics", 0.4

    monkeypatch.setattr(classify_module, "predict_with_model", fake_predict)
    result = classify_module.classify_signal(signal)

    assert result.category == "logistics"
    assert result.confidence >= 0.0


def test_uses_groq_fallback_when_distilbert_confidence_is_low(monkeypatch: object) -> None:
    signal = make_signal("Port strike disrupts shipping", "freight delay")

    calls: list[str] = []

    def fake_predict(text: str) -> tuple[str, float]:
        calls.append("distilbert")
        return "other", 0.4

    def fake_fallback(text: str) -> tuple[str, float]:
        calls.append("groq")
        return "logistics", 0.7

    monkeypatch.setattr(classify_module, "predict_with_model", fake_predict)
    monkeypatch.setattr(classify_module, "fallback_to_groq", fake_fallback)
    result = classify_module.classify_signal(signal)

    assert result.category == "logistics"
    assert result.confidence >= 0.5
    assert calls == ["distilbert", "groq"]
