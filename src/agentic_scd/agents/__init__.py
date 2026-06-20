"""Downstream agent nodes (Phase 2 walking skeleton).

Each module is a deterministic, offline **stub** of one agent — the simplest real thing
that produces a typed result and passes state forward, so the whole chain runs
end-to-end now (see specs/2026-06-19-walking-skeleton). Phases 3-7 deepen these one at a
time (Groq/DistilBERT classification, RAG impact mapping, Prophet forecasting, SimPy
simulation, RAG-grounded mitigation) behind the same node signatures.
"""

from agentic_scd.agents.schema import (
    Classification,
    Forecast,
    ImpactMap,
    Recommendation,
    Simulation,
)
