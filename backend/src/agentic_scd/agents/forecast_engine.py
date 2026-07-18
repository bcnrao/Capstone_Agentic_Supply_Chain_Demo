from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import numpy as np

from agentic_scd.config import Settings, get_settings
from agentic_scd.data.history import baseline_from_history, database_dataset_values, seed_dataset_values
from agentic_scd.db import connect, init_db
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.sqlutil import execute


def freight_seed_changes() -> list[float]:
    path = SEED_DIR / "freightos_baltic_index.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [float(row.get("change_pct", 0.0)) for row in doc.get("rows", [])]


def freight_database_changes(settings: Settings | None = None) -> list[float]:
    settings = settings or get_settings()
    if not init_db(settings):
        return []
    try:
        with connect(settings) as conn:
            token = "?" if getattr(conn, "agentic_scd_dialect", None) == "sqlite" else "%s"
            rows = execute(
                conn,
                f"SELECT raw_payload FROM signals WHERE source_type = {token} ORDER BY COALESCE(event_time, created_at), created_at",
                ("FREIGHT_INDEX",),
            ).fetchall()
    except Exception:
        return []
    changes: list[float] = []
    for row in rows:
        raw_payload = row["raw_payload"] if not isinstance(row, tuple) else row[0]
        payload = raw_payload if isinstance(raw_payload, dict) else json.loads(raw_payload or "{}")
        try:
            changes.append(float(payload.get("change_pct", 0.0)))
        except ValueError:
            continue
    return changes


def freight_pressure(settings: Settings | None = None) -> tuple[float, str]:
    changes = freight_database_changes(settings)
    if changes:
        return round(float(np.mean(changes[-4:])) / 100.0, 4), "database"
    seed = freight_seed_changes()
    if seed:
        return round(float(np.mean(seed[-4:])) / 100.0, 4), "seed_snapshot"
    return 0.0, "unavailable"


logger = logging.getLogger(__name__)


def prophet_series(horizon: int, settings: Settings | None = None) -> list[float] | None:
    values = database_dataset_values(settings) or seed_dataset_values()
    if len(values) < max(12, horizon):
        logger.warning(
            "prophet_series: insufficient data (%d points, need %d) — falling back to local_trend",
            len(values), max(12, horizon),
        )
        return None
    try:
        import pandas as pd
        from prophet import Prophet
    except Exception as exc:
        logger.warning("prophet_series: Prophet not available (%s) — falling back to local_trend", exc)
        return None
    try:
        start = date.today() - timedelta(days=7 * (len(values) - 1))
        frame = pd.DataFrame(
            {
                "ds": [start + timedelta(days=7 * idx) for idx in range(len(values))],
                "y": values,
            }
        )
        model = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
        model.fit(frame)
        future = model.make_future_dataframe(periods=horizon, freq="W")
        forecast = model.predict(future)["yhat"].tail(horizon).tolist()
        result = [round(max(10.0, float(value)), 2) for value in forecast]
        logger.info("prophet_series: fitted on %d points, returning %d-week projection", len(values), horizon)
        return result
    except Exception as exc:
        logger.warning("prophet_series: fit/predict failed (%s) — falling back to local_trend", exc)
        return None


def baseline_projection(horizon: int, settings: Settings | None = None) -> tuple[list[float], str, str]:
    projected = prophet_series(horizon, settings)
    if projected:
        _, baseline_source = baseline_from_history(horizon, settings)
        logger.info("baseline_projection: using prophet  source=%s", baseline_source)
        return projected, baseline_source, "prophet"
    baseline, baseline_source = baseline_from_history(horizon, settings)
    logger.info("baseline_projection: using local_trend  source=%s", baseline_source)
    return baseline, baseline_source, "local_trend"


def adjusted_projection(baseline: list[float], risk: float, impact_count: int, freight_delta: float, category: str = "") -> tuple[list[float], float]:
    if not baseline:
        return [], 0.0
    if risk <= 0 and impact_count <= 0:
        return [round(value, 2) for value in baseline], 0.0
    shock = max(0.0, freight_delta)
    relief = abs(min(0.0, freight_delta))
    # Category multiplier: different disruption types suppress demand differently
    # even at the same risk score.  Logistics/port delays have an immediate but
    # short-lived impact; geopolitical/tariff effects build slowly but persist;
    # labor strikes are sudden and severe; weather is acute but recovers.
    CATEGORY_MULTIPLIER: dict[str, float] = {
        "weather":       1.10,   # acute shock — moderate demand drop
        "logistics":     0.85,   # port/freight delays damp demand less than supply
        "labor_strike":  1.20,   # hardest hit — production stops immediately
        "geopolitical":  1.05,   # tariff/policy — uncertainty suppresses orders
        "quality":       0.90,   # recall risk — partial demand shift, not full drop
        "raw_material":  1.00,   # baseline
        "demand_shock":  1.15,   # demand signal itself is disrupted
        "policy":        1.05,
    }
    cat_mult = CATEGORY_MULTIPLIER.get(category.lower().strip(), 1.0)
    disruption_factor = min(0.62, risk * (0.16 + 0.022 * impact_count) * cat_mult + shock * 0.55)
    recovery_factor = min(0.12, relief * 0.2)
    horizon = len(baseline)
    adjusted = []
    for idx, value in enumerate(baseline):
        step = (idx + 1) / horizon
        recovery = recovery_factor * max(0.0, (idx - horizon / 2) / max(horizon - 1, 1))
        adjusted.append(round(max(10.0, value * (1 - disruption_factor * step + recovery)), 2))
    return adjusted, disruption_factor
