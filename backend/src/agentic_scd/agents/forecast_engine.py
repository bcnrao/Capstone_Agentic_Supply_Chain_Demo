from __future__ import annotations

import json
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


def prophet_series(horizon: int, settings: Settings | None = None) -> list[float] | None:
    values = database_dataset_values(settings) or seed_dataset_values()
    if len(values) < max(12, horizon):
        return None
    try:
        import pandas as pd
        from prophet import Prophet
    except Exception:
        return None
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
    return [round(max(10.0, float(value)), 2) for value in forecast]


def baseline_projection(horizon: int, settings: Settings | None = None) -> tuple[list[float], str, str]:
    projected = prophet_series(horizon, settings)
    if projected:
        _, baseline_source = baseline_from_history(horizon, settings)
        return projected, baseline_source, "prophet"
    baseline, baseline_source = baseline_from_history(horizon, settings)
    return baseline, baseline_source, "local_trend"


def adjusted_projection(baseline: list[float], risk: float, impact_count: int, freight_delta: float) -> tuple[list[float], float]:
    if not baseline:
        return [], 0.0
    if risk <= 0 and impact_count <= 0:
        return [round(value, 2) for value in baseline], 0.0
    shock = max(0.0, freight_delta)
    relief = abs(min(0.0, freight_delta))
    disruption_factor = min(0.62, risk * (0.16 + 0.022 * impact_count) + shock * 0.55)
    recovery_factor = min(0.12, relief * 0.2)
    horizon = len(baseline)
    adjusted = []
    for idx, value in enumerate(baseline):
        step = (idx + 1) / horizon
        recovery = recovery_factor * max(0.0, (idx - horizon / 2) / max(horizon - 1, 1))
        adjusted.append(round(max(10.0, value * (1 - disruption_factor * step + recovery)), 2))
    return adjusted, disruption_factor
