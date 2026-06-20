# Phase 2 — Thin end-to-end slice (walking skeleton) · Requirements

> Roadmap phase: **Phase 2 — Thin end-to-end slice (walking skeleton)** (see [[roadmap]]).
> Builds on the Phase 1 ingestion layer (1a/1b). Guidance: [[mission]] (capstone MVP;
> breadth + demonstrability; **always demoable**; graceful degradation), [[tech-stack]]
> (LangGraph state passing; Gradio dashboard; deterministic where the real tool is a
> later phase), and [[demo-walkthrough]] (the panel/stage layout this skeleton stands up
> in skeleton form).

## Goal

With real ingestion in place, **wire every remaining agent as a minimal stub** so the
whole chain runs end-to-end and produces one coherent result. Each stub does the
*simplest real thing* and passes typed state forward:

```
real signals (Phase 1) → classify → impact-map → forecast → simulate → recommend → render
```

The point is **breadth and integration**, not depth: prove the multi-agent path works
end-to-end and is demoable now, so Phases 3–7 can deepen one agent at a time against an
already-connected chain.

## Scope decision (confirmed)

- **Render surface:** a **minimal Gradio dashboard** ("Run pipeline" + a panel per stage),
  matching the roadmap and [[demo-walkthrough]]; Phase 8 later promotes it to the real
  dashboard and adds React + FastAPI.
- **Stub modeling:** small **typed Pydantic result models** as new `GraphState` channels;
  every stub is **pure-Python deterministic** — no LLM / Prophet / SimPy / Groq / RAG yet
  (those are Phases 3–7). Fully offline-runnable.
- **Validation:** a **one-command end-to-end run** plus **offline tests** (per-stub +
  graph-runs-end-to-end), matching the Phase 1 green-offline contract.

### In scope

1. **Shared agent result schema** (`agents/schema.py`): `Classification`, `ImpactMap`,
   `Forecast`, `Simulation`, `Recommendation` Pydantic models. Extend `GraphState`
   (`graph/state.py`) with typed channels for each (overwrite-per-run reducers).
2. **Five deterministic stub nodes** (`agents/`), each `*_node(state) -> dict`:
   - **classify** — rule/keyword category + numeric risk score + short rationale, per signal.
   - **impact-map** — hard-coded lookup (category/keyword → affected suppliers / lanes /
     facilities), per signal (the Phase 4 RAG replaces this).
   - **forecast** — trivial baseline demand vs. a risk-adjusted curve from aggregate risk.
   - **simulate** — tiny stockout-probability + revenue-impact numbers from aggregate risk.
   - **recommend** — templated actions from category + impact + simulation.
3. **Graph assembly** (`graph/builder.py`): wire
   `ingestion → input_guardrail → classify → impact → forecast → simulate → recommend → END`
   on the shared state; keep the existing `__main__` runnable and print a concise
   end-to-end summary.
4. **Always-demoable seed** — when ingestion yields **no** signals (offline / no new rows),
   top up with a deterministic **synthetic** signal (reuse `SyntheticConnector` +
   `normalize`) so the chain always shows a full result, per the [[mission]] always-demoable
   / graceful-degradation principle.
5. **Minimal Gradio dashboard** (`ui/gradio_app.py`): a "Run pipeline" button that runs the
   graph and populates one panel per stage (signals · classification · impact · forecast ·
   simulation · recommendation). Console script `agentic-scd-dashboard`.
6. **Quality + tests** (offline): per-stub unit tests (deterministic output shape/values),
   a **graph-runs-end-to-end** test (synthetic seed; no DB/network), and a dashboard-builds
   smoke. `ruff` clean.
7. **Docs & wrap-up**: README "Walking skeleton (Phase 2)" section; PR into `main`.

### Out of scope — deferred to later phases

- **Real agent implementations:** Groq classification/extraction + DistilBERT (Phase 3),
  RAG impact mapping + Chroma vector store (Phase 4), Prophet forecasting (Phase 5), SimPy +
  Monte Carlo simulation (Phase 6), RAG-grounded mitigation + **output guardrail** (Phase 7).
- **FastAPI API layer + React UI + Langfuse tracing + the evaluation panel** (Phases 8–9).
- **Interactive what-if** controls and the disruption heatmap/map (Phases 6/8).
- Phase 1c batch loaders / retention — unrelated to this slice.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Render surface | **Minimal Gradio dashboard** + a concise CLI summary on the existing entrypoint | Roadmap says "render on Gradio"; the dashboard is the visible demo, the CLI keeps `agentic-scd` coherent. React/FastAPI are Phase 8. |
| Stub fidelity | **Pure-Python deterministic** stubs (no LLM/Prophet/SimPy/RAG) | "Simplest real thing"; keeps the slice offline-runnable and lets Phases 3–7 deepen one agent at a time. |
| State contract | **Typed Pydantic result models** as new `GraphState` channels (overwrite reducer) | Gives Phases 3–7 a stable contract to fill in; mirrors the Phase 1 `new_signals` channel. |
| Always demoable | **Synthetic seed** when ingestion yields no signals | A no-DB / no-network run still shows a full end-to-end result (per [[mission]]). |
| Consumption | Per-signal for classify/impact; **aggregate** for forecast/simulate/recommend; batch loop (no `Send` fan-out) | Simplest; matches [[data-ingestion]] "downstream reads the batch and loops". |

## Context & notes

- Only the ingestion layer exists today; this phase adds the downstream agent package
  (`agents/`) and the `ui/` dashboard, and extends `graph/state.py` + `graph/builder.py`.
- Reuses Phase 0/1 building blocks: `graph.build_graph` / `GraphState`,
  `ingestion.agent.ingestion_node`, `ingestion.guardrails.input_guardrail_node`,
  `ingestion.schema.DisruptionSignal`, and `ingestion.connectors.synthetic.SyntheticConnector`
  + `ingestion.normalize.normalize` for the seed. The `llm` wrapper exists but is **not**
  called this phase.
- Everything stays **local** and offline-runnable — no cloud, no managed services, no new
  network/credential dependency (Gradio runs locally).
