# Phase 2 — Thin end-to-end slice (walking skeleton) · Plan

Numbered task groups. Each is independently reviewable; the order respects dependencies —
the shared result schema + state channels come before the stub nodes that fill them, the
nodes come before the graph that wires them, and the graph exists before the dashboard
that runs it. Scope and decisions in [[requirements]]; success criteria in [[validation]].
Stage/panel layout follows [[demo-walkthrough]].

---

## 1. Dependencies, agent result schema & state channels
1.1 `uv add gradio` (only what this slice needs; no Prophet/SimPy/Groq/Chroma yet).
1.2 `agents/schema.py` — Pydantic result models: `Classification` (signal_id, category,
    risk_score, rationale), `ImpactMap` (signal_id, affected_entities: list[str]),
    `Forecast` (baseline: list[float], adjusted: list[float], note), `Simulation`
    (stockout_probability, revenue_impact, assumptions), `Recommendation`
    (actions: list[str], summary).
1.3 Extend `graph/state.py` `GraphState` with typed channels: `classifications`,
    `impacts`, `forecast`, `simulation`, `recommendation` (overwrite-per-run, like
    `new_signals`).

## 2. Agent stub nodes (`agents/`, deterministic, typed)
Each is a pure-Python `*_node(state: GraphState) -> dict` returning its channel only.
2.1 `agents/classify.py` — per signal, map keywords → category (e.g. strike→labor,
    typhoon/earthquake→natural-disaster, tariff→policy, …) and a bounded risk score from
    keyword hits + `source_reliability`; short rationale. Reuse the disruption lexicon
    idea from `ingestion/relevance.py`.
2.2 `agents/impact.py` — per signal, a **hard-coded** category/keyword → affected
    suppliers/lanes/facilities lookup; emit `ImpactMap`s (the Phase 4 RAG replaces this).
2.3 `agents/forecast.py` — a flat baseline demand series and a risk-adjusted series that
    bends by the aggregate risk across classifications (deterministic).
2.4 `agents/simulate.py` — `stockout_probability` and `revenue_impact` as simple
    deterministic functions of aggregate risk + impact count.
2.5 `agents/recommend.py` — templated `actions` chosen by category/impact and framed by the
    simulation numbers (e.g. "shift volume to alternate supplier", "raise safety stock").

## 3. Graph assembly, synthetic seed & CLI summary
3.1 `graph/builder.py` — register the five nodes and wire
    `START → ingestion → input_guardrail → classify → impact → forecast → simulate →
    recommend → END` on `GraphState`.
3.2 **Always-demoable seed:** a small helper (e.g. `graph/seed.py` or in the run wrapper)
    that, when `new_signals` is empty after ingestion, injects one deterministic synthetic
    `DisruptionSignal` (reuse `SyntheticConnector` + `normalize`) so the chain always has
    input. Wire it as a step right after the guardrail (or in `run()`), guarded so it only
    fires on empty.
3.3 `__main__.py` — keep `agentic-scd` running the full graph and print a concise
    end-to-end summary (signals kept → top classification → impacts → forecast delta →
    sim numbers → recommended actions).

## 4. Minimal Gradio dashboard
4.1 `ui/gradio_app.py` — a Gradio Blocks app: a **"Run pipeline"** button (+ a
    live/cached/synthetic scenario selector, minimal) that calls the graph `run()` and
    renders one panel per stage: signals, classification, impact, forecast (baseline vs
    adjusted), simulation, recommendation. A simple stage-completion list stands in for the
    run-status strip (full strip + heatmap are Phase 8).
4.2 `build_dashboard()` returns the app (importable for a build smoke); `main()` launches
    it. Console script `agentic-scd-dashboard = "agentic_scd.ui.gradio_app:main"`.

## 5. Quality baseline & tests (offline)
5.1 `pytest`, all offline (no DB/network):
    - per-stub unit tests: each node turns a small fixed input state into the expected
      typed output (category mapping, impact lookup, forecast bend, sim numbers, actions);
    - **graph end-to-end**: `run()` with the synthetic seed yields a state carrying
      `new_signals` + all five downstream channels populated and well-typed;
    - **dashboard builds**: `build_dashboard()` constructs without launching a server.
5.2 `ruff check` + `ruff format --check` clean across the tree.

## 6. Docs & wrap-up
6.1 README "Walking skeleton (Phase 2)" section: `uv run agentic-scd` (one-command
    end-to-end summary) and `uv run agentic-scd-dashboard` (Gradio); what each stub does
    and that Phases 3–7 deepen them; the synthetic-seed always-demoable note.
6.2 Confirm all [[validation]] criteria pass; open a PR from `phase-2-walking-skeleton`
    into `main`.
