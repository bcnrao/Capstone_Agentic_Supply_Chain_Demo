"""Tests for the forecast agent and its integration with the simulation engine.

Coverage:
  - build_forecast() output schema and field ranges
  - Prophet vs local_trend model selection
  - Disruption ratio correctly suppresses demand under risk
  - inventory_days_left scales inversely with risk
  - forecast_node wires into GraphState correctly
  - sim_engine consumes forecast via disruption ratio (not raw weekly values)
  - HIGH path (no forecast) vs MEDIUM path (with forecast) demand values
  - demand_deviation_pct sign and magnitude
  - mape_estimate is non-negative and bounded
  - freight_pressure_pct is present
"""
from __future__ import annotations

import numpy as np
import pytest

from agentic_scd.agents.forecast import aggregate_risk, build_forecast, forecast_node
from agentic_scd.agents.schema import Classification, Forecast, ImpactMap
from agentic_scd.agents.sim_engine import KAGGLE_DAILY_DEMAND, run_discrete_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cls(severity: float, category: str = "weather") -> Classification:
    return Classification(
        signal_id="test",
        category=category,
        risk_score=round(severity / 10.0, 4),
        severity=severity,
    )


def _impact(lanes: list[str] | None = None) -> ImpactMap:
    return ImpactMap(
        signal_id="test",
        affected_suppliers=["Supplier A"],
        affected_lanes=lanes or ["Shanghai-Los Angeles"],
        affected_facilities=["Los Angeles Import DC"],
    )


def _forecast_with_risk(risk_severity: float) -> Forecast:
    return build_forecast([_cls(risk_severity)], [_impact()])


# ---------------------------------------------------------------------------
# 1. Output schema and field presence
# ---------------------------------------------------------------------------

def test_forecast_returns_forecast_object():
    f = _forecast_with_risk(5.0)
    assert isinstance(f, Forecast)


def test_forecast_has_eight_weekly_dates():
    f = _forecast_with_risk(5.0)
    assert len(f.dates) == 8
    assert len(f.baseline) == 8
    assert len(f.adjusted) == 8


def test_forecast_baseline_all_positive():
    f = _forecast_with_risk(5.0)
    assert all(v > 0 for v in f.baseline), "All baseline values must be positive"


def test_forecast_adjusted_all_positive():
    f = _forecast_with_risk(8.0)
    assert all(v > 0 for v in f.adjusted), "All adjusted values must be positive under high risk"


def test_forecast_model_name_is_known_value():
    f = _forecast_with_risk(5.0)
    assert f.model_name in {"prophet", "local_trend"}, f"Unexpected model: {f.model_name}"


def test_forecast_mape_non_negative_and_bounded():
    f = _forecast_with_risk(6.0)
    assert 0.0 <= f.mape_estimate <= 1.0, f"MAPE out of range: {f.mape_estimate}"


def test_forecast_freight_pressure_present():
    f = _forecast_with_risk(5.0)
    # freight_pressure_pct is a float (may be 0 if no freight data available)
    assert isinstance(f.freight_pressure_pct, float)


def test_forecast_note_mentions_model():
    f = _forecast_with_risk(5.0)
    assert f.model_name in f.note, "note should mention the model used"


# ---------------------------------------------------------------------------
# 2. Disruption signal: adjusted < baseline under meaningful risk
# ---------------------------------------------------------------------------

def test_high_risk_suppresses_adjusted_demand():
    """At high risk, adjusted demand should be lower than baseline."""
    f = _forecast_with_risk(8.0)
    assert np.mean(f.adjusted) < np.mean(f.baseline), (
        "Adjusted demand must be lower than baseline at high risk"
    )


def test_low_risk_adjusted_close_to_baseline():
    """At near-zero risk, adjusted should be very close to baseline."""
    f = _forecast_with_risk(1.0)
    ratio = np.mean(f.adjusted) / np.mean(f.baseline)
    assert ratio > 0.95, f"Low-risk suppression too strong: ratio={ratio:.3f}"


def test_demand_deviation_negative_under_risk():
    """demand_deviation_pct should be negative when disruption suppresses demand."""
    f = _forecast_with_risk(7.0)
    assert f.demand_deviation_pct < 0.0, (
        f"Expected negative deviation under high risk, got {f.demand_deviation_pct}"
    )


def test_demand_deviation_magnitude_scales_with_risk():
    """Higher risk should produce larger negative deviation."""
    f_low  = _forecast_with_risk(2.0)
    f_high = _forecast_with_risk(9.0)
    assert f_high.demand_deviation_pct < f_low.demand_deviation_pct, (
        "High-risk deviation should be more negative than low-risk"
    )


# ---------------------------------------------------------------------------
# 3. inventory_days_left scales inversely with risk
# ---------------------------------------------------------------------------

def test_inventory_days_positive():
    f = _forecast_with_risk(5.0)
    assert f.inventory_days_left > 0.0


def test_high_risk_lower_inventory_days_than_low_risk():
    f_low  = _forecast_with_risk(1.5)
    f_high = _forecast_with_risk(9.0)
    assert f_high.inventory_days_left < f_low.inventory_days_left, (
        "High-risk scenario should have fewer inventory days remaining"
    )


def test_inventory_days_zero_risk_near_maximum():
    """At risk=0, inventory_days_left = 26*(1-0)+4 = 30."""
    f = build_forecast([], [])   # no classifications → risk = 0
    assert f.inventory_days_left >= 28.0, f"Got {f.inventory_days_left}"


# ---------------------------------------------------------------------------
# 4. predicted_delay_days
# ---------------------------------------------------------------------------

def test_predicted_delay_non_negative():
    f = _forecast_with_risk(6.0)
    assert f.predicted_delay_days >= 0.0


def test_predicted_delay_scales_with_risk():
    f_low  = _forecast_with_risk(1.0)
    f_high = _forecast_with_risk(9.0)
    assert f_high.predicted_delay_days > f_low.predicted_delay_days


# ---------------------------------------------------------------------------
# 5. Zero-risk edge case
# ---------------------------------------------------------------------------

def test_zero_risk_no_classifications():
    f = build_forecast([], [])
    assert f.demand_deviation_pct >= -5.0, "Near-zero deviation expected at zero risk"
    assert f.inventory_days_left >= 28.0


def test_zero_risk_adjusted_equals_baseline_approximately():
    f = build_forecast([], [])
    ratio = np.mean(f.adjusted) / np.mean(f.baseline)
    assert ratio > 0.97, f"Zero-risk ratio too low: {ratio:.3f}"


# ---------------------------------------------------------------------------
# 6. forecast_node wires into GraphState
# ---------------------------------------------------------------------------

def test_forecast_node_returns_forecast_key():
    state = {
        "classifications": [_cls(6.0)],
        "impacts": [_impact()],
    }
    result = forecast_node(state)
    assert "forecast" in result
    assert isinstance(result["forecast"], Forecast)


def test_forecast_node_empty_state():
    result = forecast_node({})
    assert "forecast" in result
    f = result["forecast"]
    assert len(f.baseline) == 8


# ---------------------------------------------------------------------------
# 7. aggregate_risk helper
# ---------------------------------------------------------------------------

def test_aggregate_risk_empty():
    assert aggregate_risk([]) == 0.0


def test_aggregate_risk_single():
    assert aggregate_risk([_cls(7.0)]) == pytest.approx(0.7, abs=0.01)


def test_aggregate_risk_mean_of_multiple():
    risk = aggregate_risk([_cls(4.0), _cls(8.0)])
    assert risk == pytest.approx(0.6, abs=0.01)


# ---------------------------------------------------------------------------
# 8. sim_engine consumes forecast via disruption ratio — not raw weekly values
# ---------------------------------------------------------------------------

def test_sim_with_forecast_daily_demand_stays_in_calibrated_range():
    """daily_demand inside sim_engine must stay near 30 u/d regardless of
    Prophet's raw weekly output (~720/week = 103/day)."""
    f = _forecast_with_risk(7.0)
    result = run_discrete_event([_cls(7.0)], [_impact()], f, iterations=50)
    # Extract daily_demand from assumptions string
    assumptions = result["assumptions"]
    # Format: "... daily demand 26 units; ..."
    daily_str = assumptions.split("daily demand ")[1].split(" units")[0]
    daily = float(daily_str)
    assert 10.0 <= daily <= 50.0, (
        f"daily_demand={daily} is outside calibrated range 10-50 u/d. "
        f"Likely using raw weekly forecast values instead of disruption ratio."
    )


def test_sim_forecast_disruption_reduces_daily_demand_vs_no_forecast():
    """With a high-risk forecast, adjusted daily demand should be slightly
    lower than the Kaggle constant used when no forecast is provided."""
    f = _forecast_with_risk(8.0)
    result_with = run_discrete_event([_cls(8.0)], [_impact()], f, iterations=50)
    result_none = run_discrete_event([_cls(8.0)], [_impact()], None, iterations=50)

    daily_with = float(result_with["assumptions"].split("daily demand ")[1].split(" units")[0])
    daily_none = float(result_none["assumptions"].split("daily demand ")[1].split(" units")[0])

    # With forecast disruption ratio < 1.0, daily_with should be ≤ daily_none
    assert daily_with <= daily_none + 2.0, (
        f"Forecast-derived demand ({daily_with}) should not exceed no-forecast demand ({daily_none})"
    )


def test_sim_low_risk_forecast_demand_close_to_kaggle_constant():
    """At low risk, disruption_ratio ≈ 0.98, so daily_demand ≈ 30 u/d."""
    f = _forecast_with_risk(1.5)
    result = run_discrete_event([_cls(1.5)], [_impact()], f, iterations=50)
    daily_str = result["assumptions"].split("daily demand ")[1].split(" units")[0]
    daily = float(daily_str)
    assert abs(daily - KAGGLE_DAILY_DEMAND) <= 5.0, (
        f"Low-risk demand {daily} should be close to Kaggle constant {KAGGLE_DAILY_DEMAND}"
    )


def test_sim_with_and_without_forecast_same_output_schema():
    """Forecast presence should not change the output dict structure."""
    f = _forecast_with_risk(6.0)
    r_with = run_discrete_event([_cls(6.0)], [_impact()], f, 30)
    r_none = run_discrete_event([_cls(6.0)], [_impact()], None, 30)
    assert set(r_with.keys()) == set(r_none.keys())


# ---------------------------------------------------------------------------
# 9. HIGH path (no forecast) vs MEDIUM path (with forecast) gradient preserved
# ---------------------------------------------------------------------------

def test_high_path_no_forecast_still_produces_valid_simulation():
    """HIGH path bypasses forecast; simulate_node receives forecast=None."""
    result = run_discrete_event([_cls(9.0)], [_impact()], None, iterations=100)
    assert 0.0 <= result["stockout_probability"] <= 1.0
    assert result["service_level"] >= 0.0


def test_medium_path_with_forecast_higher_stockout_than_low_risk():
    """Medium risk with forecast should produce higher stockout than low risk with forecast."""
    f_med = _forecast_with_risk(6.0)
    f_low = _forecast_with_risk(1.5)
    r_med = run_discrete_event([_cls(6.0)], [_impact()], f_med, iterations=150)
    r_low = run_discrete_event([_cls(1.5)], [_impact()], f_low, iterations=150)
    assert r_med["stockout_probability"] >= r_low["stockout_probability"], (
        f"Medium risk ({r_med['stockout_probability']:.0%}) should be >= "
        f"low risk ({r_low['stockout_probability']:.0%})"
    )


def test_forecast_does_not_break_service_level_range():
    f = _forecast_with_risk(5.0)
    result = run_discrete_event([_cls(5.0)], [_impact()], f, iterations=100)
    assert 0.0 <= result["service_level"] <= 1.0


def test_forecast_does_not_break_p90_gte_p50():
    f = _forecast_with_risk(6.5)
    result = run_discrete_event([_cls(6.5)], [_impact()], f, iterations=100)
    assert result["revenue_loss_p90"] >= result["revenue_loss_p50"]
