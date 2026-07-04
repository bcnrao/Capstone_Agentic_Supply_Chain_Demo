from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from agentic_scd.config import Settings, get_settings
from agentic_scd.db import connect, init_db
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.sqlutil import execute


def default_baseline(horizon: int) -> list[float]:
    return [1000.0 + 35 * idx for idx in range(horizon)]


def compress(values: list[float], horizon: int) -> list[float]:
    if not values:
        return default_baseline(horizon)
    series = np.array(values, dtype=float)
    if len(series) == 1:
        baseline = [float(series[0]) for _ in range(horizon)]
    elif len(series) < horizon:
        baseline = np.interp(
            np.linspace(0, len(series) - 1, num=horizon),
            np.arange(len(series)),
            series,
        ).tolist()
    else:
        chunks = np.array_split(series, horizon)
        baseline = [float(np.mean(chunk)) for chunk in chunks]
    trend = np.polyfit(np.arange(len(baseline)), baseline, 1)[0] if len(baseline) > 1 else 0.0
    return [round(max(10.0, baseline[idx] + 0.25 * trend * idx), 2) for idx in range(horizon)]


def parse_json(value) -> dict:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def seed_dataset_values(path: Path | None = None) -> list[float]:
    csv_path = path or SEED_DIR / "supply_chain_dataset.csv"
    if not csv_path.exists():
        return []
    values: list[float] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                demand = float(row.get("Number of products sold", 0))
                stock = float(row.get("Stock levels", 0))
                values.append(max(10.0, demand + 0.35 * stock))
            except ValueError:
                continue
    return values


def database_dataset_values(settings: Settings | None = None) -> list[float]:
    settings = settings or get_settings()
    if not init_db(settings):
        return []
    try:
        with connect(settings) as conn:
            token = "?" if getattr(conn, "agentic_scd_dialect", None) == "sqlite" else "%s"
            rows = execute(
                conn,
                f"SELECT raw_payload FROM signals WHERE source_type = {token} ORDER BY COALESCE(event_time, created_at), created_at",
                ("DATASET",),
            ).fetchall()
    except Exception:
        return []
    values: list[float] = []
    for row in rows:
        raw_payload = row["raw_payload"] if not isinstance(row, tuple) else row[0]
        payload = parse_json(raw_payload)
        if str(payload.get("kind", "")).lower() != "demand":
            continue
        units = payload.get("demand_units") or payload.get("Number of products sold")
        stock = payload.get("stock_units") or payload.get("stock_levels") or payload.get("Stock levels") or 0
        try:
            demand = float(units or 0)
            stock_units = float(stock or 0)
        except ValueError:
            continue
        values.append(max(10.0, demand + 0.35 * stock_units))
    return values


def baseline_from_history(horizon: int, settings: Settings | None = None) -> tuple[list[float], str]:
    db_values = database_dataset_values(settings)
    if db_values:
        return compress(db_values, horizon), "database"
    seed_values = seed_dataset_values()
    if seed_values:
        return compress(seed_values, horizon), "seed_csv"
    return default_baseline(horizon), "synthetic"
