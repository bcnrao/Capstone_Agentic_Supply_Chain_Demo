"""SimPy discrete-event simulation engine implementation.

Replaces the heap-queue prototype with a proper SimPy 4-node supply chain
model: Supplier → Port → Warehouse → Retailer.

Each node is modelled as a SimPy Resource whose capacity is reduced by the
aggregate risk score.  A configurable number of Monte Carlo iterations run
the same 30-day simulation window with different random seeds so we get a
probability distribution rather than a single point estimate.

Network parameters are calibrated from:
  - network.json  : transit days per lane (Shanghai-LA = 17d, Mumbai-Rotterdam = 21d, etc.)
  - supply_chain_dataset.csv (Kaggle EDA) :
        lead_time mean = 16 days, std ≈ 8.8 days
        defect_rate base  = 0.36  (36 % inspection failure rate)
        stock levels mean = 47.8 units → used to seed inventory

Public interface (unchanged from the prototype):
    run_discrete_event(
        classifications : list[Classification],
        impacts         : list[ImpactMap],
        forecast        : Forecast | None,
        iterations      : int,
    ) -> dict[str, float | int | str]

All keys in the returned dict match the Simulation schema in schema.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from agentic_scd.agents.forecast import aggregate_risk
from agentic_scd.agents.schema import Classification, Forecast, ImpactMap
from agentic_scd.ingestion.paths import SEED_DIR

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Network constants — sourced from network.json
# ---------------------------------------------------------------------------

#: Transit days for each lane in the seed network
LANE_DAYS: dict[str, float] = {
    "Shanghai-Los Angeles":    17.0,
    "Ho Chi Minh-Los Angeles": 19.0,
    "Mumbai-Rotterdam":        21.0,
    "Rotterdam-New York":      13.0,
    "Los Angeles-Dallas":       4.0,
    "Mumbai-Dubai":             2.0,
}
DEFAULT_TRANSIT_DAYS = 17.0   # fallback when no lane is matched

# ---------------------------------------------------------------------------
# Kaggle EDA calibration constants
# ---------------------------------------------------------------------------

KAGGLE_LEAD_TIME_MEAN  = 16.0   # days — from dataset EDA
KAGGLE_LEAD_TIME_STD   =  8.8   # days — from dataset EDA
KAGGLE_DEFECT_RATE     =  0.36  # fraction — 36 % inspection failure rate
KAGGLE_STOCK_MEAN      = 47.8   # units — mean stock level across 100 records
KAGGLE_DAILY_DEMAND    = 30.0   # units/day — approx (≈ 900 units/month baseline)

# ---------------------------------------------------------------------------
# Simulation window
# ---------------------------------------------------------------------------

SIM_DAYS          = 30    # one-month window per iteration
SHIPMENTS_PER_RUN = 3    # number of shipments injected per iteration
REVENUE_PER_UNIT  = 18.0  # ₹ per unit short (from existing engine)

# Each shipment covers this many days of demand.
# 3 shipments × 5 days = 15 days supply, leaving a 15-day gap that must come
# from opening inventory.  Delays and defects erode both — by design.
DAYS_SUPPLY_PER_SHIPMENT = 5


# ---------------------------------------------------------------------------
# Helper: read network.json for dynamic lane calibration
# ---------------------------------------------------------------------------

def _load_network() -> dict:
    path = SEED_DIR / "network.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _extract_transit_days(impacts: list[ImpactMap]) -> float:
    """Return the mean transit days for the affected lanes, falling back to
    the dataset default if none can be matched."""
    network = _load_network()
    lane_map: dict[str, float] = {
        row["name"]: float(row.get("days", DEFAULT_TRANSIT_DAYS))
        for row in network.get("lanes", [])
        if "name" in row
    }
    lane_map.update(LANE_DAYS)  # seed constants take precedence

    days_list: list[float] = []
    for impact in impacts:
        for lane in impact.affected_lanes:
            if lane in lane_map:
                days_list.append(lane_map[lane])

    return float(np.mean(days_list)) if days_list else DEFAULT_TRANSIT_DAYS


def _extract_supplier_reliability(impacts: list[ImpactMap]) -> float:
    """Return mean supplier reliability from network.json for the affected
    suppliers, defaulting to 0.80 (average of the five seed suppliers)."""
    network = _load_network()
    rel_map: dict[str, float] = {
        row["name"]: float(row.get("reliability", 0.80))
        for row in network.get("suppliers", [])
        if "name" in row
    }
    values: list[float] = []
    for impact in impacts:
        for supplier in impact.affected_suppliers:
            if supplier in rel_map:
                values.append(rel_map[supplier])
    return float(np.mean(values)) if values else 0.80


# ---------------------------------------------------------------------------
# Core SimPy iteration
# ---------------------------------------------------------------------------

def _run_one_iteration(
    rng: np.random.Generator,
    risk: float,
    transit_days: float,
    supplier_reliability: float,
    defect_rate: float,
    inventory: float,
    daily_demand: float,
    n_affected_nodes: int,
) -> tuple[bool, float, float, float, float]:
    """Simulate one 30-day window and return
    (stockout_occurred, shortage_units, revenue_lost, recovery_days, service_level).

    Uses SimPy for the 4-node discrete-event model.
    Falls back to a pure-numpy calculation if SimPy is not installed.
    """
    try:
        import simpy
        return _simpy_iteration(
            rng, risk, transit_days, supplier_reliability,
            defect_rate, inventory, daily_demand, n_affected_nodes,
        )
    except ImportError:
        return _numpy_fallback_iteration(
            rng, risk, transit_days, supplier_reliability,
            defect_rate, inventory, daily_demand, n_affected_nodes,
        )


def _simpy_iteration(
    rng: np.random.Generator,
    risk: float,
    transit_days: float,
    supplier_reliability: float,
    defect_rate: float,
    inventory: float,
    daily_demand: float,
    n_affected_nodes: int,
) -> tuple[bool, float, float, float, float]:
    """SimPy implementation of the 4-node supply chain model.

    Nodes
    -----
    1. Supplier   — processes orders; capacity reduced by risk and reliability
    2. Port       — clears shipments; capacity reduced by risk
    3. Warehouse  — receives stock; ample capacity
    4. Retailer   — consumes daily demand from warehouse stock

    Shipment design
    ---------------
    We inject SHIPMENTS_PER_RUN shipments at staggered start times within the
    simulation window.  This ensures some shipments can arrive before day 30
    even though full transit takes 17+ days, while delayed or stuck shipments
    cause realistic shortages.

    Disruption mechanics
    --------------------
    * Supplier capacity = max(1, floor(3 × (1 − risk) × reliability))
    * Port capacity     = max(1, floor(5 × (1 − risk × 0.7)))
    * Port delay        = Exponential(base + risk × amplifier) — bounded by risk
    * Transit time      = Normal(transit_days, transit_days × 0.15) [clamped ≥ 1]
    * Defect rate       = base_rate × risk  — fraction of each shipment lost
    * Demand drains inventory daily; unmet demand is shortage
    """
    import simpy  # noqa: PLC0415 — imported after availability check

    # --- node capacities ---
    supplier_cap = max(1, int(3 * (1 - risk) * supplier_reliability))
    port_cap     = max(1, int(5 * (1 - risk * 0.7)))

    env       = simpy.Environment()
    supplier  = simpy.Resource(env, capacity=supplier_cap)
    port      = simpy.Resource(env, capacity=port_cap)
    warehouse = simpy.Resource(env, capacity=50)

    state = {
        "inventory": inventory,
        "shortage":  0.0,
        "delay_sum": 0.0,  # cumulative delay across all shipments
        "ships_completed": 0,
    }

    # --- shipment process ---
    # Each shipment starts at a staggered offset so the first one can arrive
    # within the 30-day window (offset=0 → arrives ~port_delay days in).
    def shipment_process(env: simpy.Environment, start_offset: float, units: float) -> object:  # type: ignore[type-arg]
        yield env.timeout(start_offset)

        t_start = env.now

        # 1. Supplier processing — scaled by lead time, compressed by capacity
        lead_time = max(
            0.5,
            float(rng.normal(
                KAGGLE_LEAD_TIME_MEAN / max(1, supplier_cap),
                KAGGLE_LEAD_TIME_STD / max(1, supplier_cap),
            )),
        )
        with supplier.request() as req:
            yield req
            yield env.timeout(lead_time)

        # 2. Port clearance — extended by risk and congestion
        port_delay = max(
            0.5,
            float(rng.exponential(1.5 + risk * 4.0 + 0.3 * n_affected_nodes)),
        )
        with port.request() as req:
            yield req
            yield env.timeout(port_delay)

        # 3. Transit
        transit = max(
            1.0,
            float(rng.normal(transit_days * 0.6, transit_days * 0.15)),
        )
        yield env.timeout(transit)

        # 4. Warehouse receipt
        total_delay = env.now - t_start
        state["delay_sum"] += total_delay
        state["ships_completed"] += 1

        units_good = units * max(0.0, 1.0 - defect_rate)
        with warehouse.request() as req:
            yield req
            yield env.timeout(0.25)
            state["inventory"] += units_good

    # --- daily demand drain ---
    def demand_drain(env: simpy.Environment) -> object:  # type: ignore[type-arg]
        while True:
            yield env.timeout(1.0)
            if state["inventory"] >= daily_demand:
                state["inventory"] -= daily_demand
            else:
                state["shortage"] += daily_demand - state["inventory"]
                state["inventory"] = 0.0

    # Stagger shipment starts evenly across the window.
    # units_per_ship covers enough demand to replenish between shipments.
    units_per_ship = daily_demand * (SIM_DAYS / SHIPMENTS_PER_RUN)
    for idx in range(SHIPMENTS_PER_RUN):
        offset = idx * (SIM_DAYS / SHIPMENTS_PER_RUN) * 0.15  # small stagger
        env.process(shipment_process(env, offset, units_per_ship))

    env.process(demand_drain(env))
    env.run(until=float(SIM_DAYS))

    shortage   = state["shortage"]
    stockout   = shortage > 0.0
    revenue    = shortage * REVENUE_PER_UNIT
    n_comp     = max(1, state["ships_completed"])
    avg_delay  = state["delay_sum"] / n_comp
    recovery   = avg_delay + 1.5 + risk * 5.5
    total_dem  = daily_demand * SIM_DAYS
    svc_level  = max(0.0, 1.0 - shortage / max(total_dem, 1.0))

    return stockout, shortage, revenue, recovery, svc_level


def _numpy_fallback_iteration(
    rng: np.random.Generator,
    risk: float,
    transit_days: float,
    supplier_reliability: float,
    defect_rate: float,
    inventory: float,
    daily_demand: float,
    n_affected_nodes: int,
) -> tuple[bool, float, float, float, float]:
    """Pure-numpy fallback when SimPy is not installed.

    Approximates the SimPy model with a vectorised daily simulation:
    each day draws a random supply arrival and demand draw, accumulating
    shortages when demand exceeds supply + inventory.
    """
    days           = SIM_DAYS
    supply_per_day = (daily_demand * days / SHIPMENTS_PER_RUN) / (transit_days + 2.0)
    capacity_factor = max(0.05, (1.0 - risk) * supplier_reliability)
    effective_supply = supply_per_day * capacity_factor * (1.0 - defect_rate * risk)

    arrivals = rng.poisson(effective_supply, size=days)
    demands  = rng.poisson(daily_demand, size=days)
    inv      = inventory
    shortage = 0.0
    for arr, dem in zip(arrivals, demands, strict=False):
        inv += float(arr)
        dem_f = float(dem)
        if inv >= dem_f:
            inv -= dem_f
        else:
            shortage += dem_f - inv
            inv = 0.0

    stockout      = shortage > 0.0
    revenue_lost  = shortage * REVENUE_PER_UNIT
    recovery_days = transit_days + 1.5 + risk * 5.5 + n_affected_nodes * 0.5
    service_level = max(0.0, 1.0 - shortage / max(daily_demand * days, 1.0))
    return stockout, shortage, revenue_lost, recovery_days, service_level


# ---------------------------------------------------------------------------
# Public entry point — called by simulate.py (signature must not change)
# ---------------------------------------------------------------------------

def run_discrete_event(
    classifications: list[Classification],
    impacts: list[ImpactMap],
    forecast: Forecast | None,
    iterations: int,
) -> dict[str, float | int | str]:
    """Run a Monte Carlo supply chain simulation and return a results dict.

    Parameters
    ----------
    classifications:
        Risk classification output from classify_node.  Used to derive
        aggregate risk score and routing path.
    impacts:
        Impact mapping output from impact_node.  Used to identify affected
        suppliers and lanes so we can calibrate transit times and reliability.
    forecast:
        Forecast output from forecast_node (may be None on the HIGH path
        where forecast_node is bypassed).  Provides baseline and adjusted
        demand series plus inventory_days_left.
    iterations:
        Number of Monte Carlo iterations.  Set via SIMULATION_ITERATIONS env
        var (default 300).  Proposal target for demo: 200.

    Returns
    -------
    dict matching the Simulation schema in schema.py:
        stockout_probability, revenue_impact, recovery_time_days,
        service_level, expected_shortage_units, iterations, assumptions,
        revenue_loss_p50, revenue_loss_p90, engine.
    """
    risk      = aggregate_risk(classifications)
    affected  = sum(len(item.affected_entities) for item in impacts)
    n_iters   = max(1, iterations)

    # --- demand calibration ---
    if forecast and forecast.baseline:
        baseline_demand = float(np.mean(forecast.baseline))
    else:
        baseline_demand = KAGGLE_DAILY_DEMAND * SIM_DAYS   # monthly baseline

    if forecast and forecast.adjusted:
        adjusted_demand = float(np.mean(forecast.adjusted))
    else:
        adjusted_demand = baseline_demand * max(0.0, 1.0 - 0.18 * risk)

    daily_demand = max(1.0, adjusted_demand / SIM_DAYS)

    # opening inventory — must cover the replenishment lead time at zero risk
    # so healthy scenarios don't show false stockouts.
    # Base = transit_days + lead_time (≈ 10 + 8 = 18 days of demand) at risk=0.
    # Risk erodes it: at risk=1.0, only 15 % of safety stock remains.
    _forecast_inv_days = (
        max(1.0, forecast.inventory_days_left)
        if (forecast and forecast.inventory_days_left)
        else 20.0
    )
    transit = _extract_transit_days(impacts) * 0.6   # compressed transit
    # Cover must be ≥ transit + half lead-time so the first shipment arrives
    # before stock runs out at zero risk.  Add a 4-day safety buffer.
    nominal_cover_days = max(
        transit + KAGGLE_LEAD_TIME_MEAN / 2 + 4.0,
        _forecast_inv_days,
    )
    risk_factor = max(0.15, 1.0 - 0.85 * risk)
    inventory_start = daily_demand * nominal_cover_days * risk_factor

    # --- network calibration from impact data ---
    transit_days         = _extract_transit_days(impacts)
    supplier_reliability = _extract_supplier_reliability(impacts)

    # defect rate scales with risk (base 36 % from Kaggle, amplified by risk)
    defect_rate = min(0.95, KAGGLE_DEFECT_RATE + 0.4 * risk)

    # --- Monte Carlo ---
    # Deterministic seed so the same scenario produces the same output;
    # varied enough across different risk levels to spread the distribution.
    seed = 42 + int(risk * 1000) + affected + int(baseline_demand) % 97
    rng  = np.random.default_rng(seed)

    stockouts:     list[float] = []
    shortages:     list[float] = []
    revenues:      list[float] = []
    recoveries:    list[float] = []
    service_levels: list[float] = []

    for _ in range(n_iters):
        stockout, shortage, revenue, recovery, sl = _run_one_iteration(
            rng,
            risk,
            transit_days,
            supplier_reliability,
            defect_rate,
            inventory_start,
            daily_demand,
            affected,
        )
        stockouts.append(float(stockout))
        shortages.append(shortage)
        revenues.append(revenue)
        recoveries.append(recovery)
        service_levels.append(sl)

    # --- aggregate statistics ---
    stockout_prob   = float(np.mean(stockouts))
    mean_revenue    = float(np.mean(revenues))
    p80_recovery    = float(np.percentile(recoveries, 80))
    mean_service    = float(np.mean(service_levels))
    mean_shortage   = float(np.mean(shortages))
    p50_revenue     = float(np.percentile(revenues, 50))
    p90_revenue     = float(np.percentile(revenues, 90))

    # detect which engine ran
    try:
        import simpy as _simpy  # noqa: F401, PLC0415
        engine_label = "simpy_monte_carlo"
    except ImportError:
        engine_label = "numpy_fallback_monte_carlo"

    assumptions = (
        f"{n_iters} {engine_label} iterations; "
        f"aggregate risk {risk:.2f}; "
        f"affected nodes {affected}; "
        f"transit days {transit_days:.0f}; "
        f"supplier reliability {supplier_reliability:.2f}; "
        f"defect rate {defect_rate:.0%}; "
        f"daily demand {daily_demand:.0f} units; "
        f"opening inventory {inventory_start:.0f} units."
    )

    return {
        "stockout_probability":    round(stockout_prob, 4),
        "revenue_impact":          round(mean_revenue, 2),
        "recovery_time_days":      round(p80_recovery, 1),
        "service_level":           round(mean_service, 4),
        "expected_shortage_units": round(mean_shortage, 2),
        "iterations":              n_iters,
        "assumptions":             assumptions,
        "revenue_loss_p50":        round(p50_revenue, 2),
        "revenue_loss_p90":        round(p90_revenue, 2),
        "engine":                  engine_label,
    }
