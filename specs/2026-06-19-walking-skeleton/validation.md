# Phase 2 — Thin end-to-end slice (walking skeleton) · Validation

How to know the implementation succeeded and the branch can merge. Maps to the task
groups in [[plan]] and the scope in [[requirements]]. The roadmap "Done when" for Phase 2
is the north star: **one command runs ingest(real) → classify → impact-map → forecast →
simulate → recommend → dashboard and shows a result end-to-end.**

## Acceptance criteria

### A. End-to-end graph (offline, deterministic)
- [ ] `uv run agentic-scd` runs the full chain
      `ingestion → input_guardrail → classify → impact → forecast → simulate → recommend`
      and prints a concise end-to-end summary — **with no DB and no network**, never
      crashing.
- [ ] The returned `GraphState` carries `new_signals` plus all five downstream channels
      (`classifications`, `impacts`, `forecast`, `simulation`, `recommendation`), each a
      valid typed model (not `None`/empty).
- [ ] Re-running is **deterministic** for a fixed seed (same synthetic input → same
      classification/impact/forecast/sim/recommendation).

### B. Stub correctness (per node)
- [ ] **classify** assigns a sensible category + bounded risk score for a clear signal
      (e.g. "port strike" → labor/logistics, score in range) with a rationale.
- [ ] **impact-map** returns concrete affected entities (suppliers/lanes/facilities) from
      the hard-coded lookup for a classified signal.
- [ ] **forecast** produces a baseline and a **risk-adjusted** series that differs from the
      baseline when risk is present (the curve visibly bends).
- [ ] **simulate** returns a `stockout_probability` in `[0,1]` and a `revenue_impact` that
      scales with aggregate risk.
- [ ] **recommend** returns at least one templated action tied to the category/impact.

### C. Always demoable (graceful degradation)
- [ ] With **no signals** from ingestion (no DB / no new rows), the synthetic **seed**
      injects a deterministic signal so the chain still produces a full result — a fully
      offline `agentic-scd` run shows every stage populated.
- [ ] No live source / DB is required for the demo path; nothing raises.

### D. Dashboard (render surface)
- [ ] `uv run agentic-scd-dashboard` launches a Gradio app with a **"Run pipeline"** button
      that runs the graph and populates one panel per stage (signals · classification ·
      impact · forecast · simulation · recommendation).
- [ ] `build_dashboard()` constructs the app **without** launching a server (importable for
      the build smoke test).

### E. Quality gates
- [ ] `uv run pytest` passes **with no DB and no network** (per-stub tests, the graph
      end-to-end test, and the dashboard-builds smoke run offline; any DB-touching tests
      skip cleanly).
- [ ] `uv run ruff check` and `uv run ruff format --check` are clean across the tree.
- [ ] The new runtime dep (`gradio`) is in `pyproject.toml` / `uv.lock`; nothing
      cloud/managed and no Prophet/SimPy/Groq/Chroma pulled in yet.

## Manual smoke test

```bash
uv run agentic-scd                 # end-to-end summary: signals -> ... -> recommendation
#   expect: every stage printed, even offline (synthetic seed guarantees a result)

uv run agentic-scd-dashboard       # open the Gradio URL, click "Run pipeline"
#   expect: each panel populates (signals, classification, impact, forecast, sim, recommend)
```

With Postgres up and signals collected, the same run shows **real** ingested signals
flowing through the stubs instead of the synthetic seed:

```bash
docker compose up -d postgres && uv run agentic-scd-collect   # persist real signals
uv run agentic-scd                                            # real signals -> stubs -> result
```

## Definition of done
- [ ] All acceptance criteria (A–E) checked.
- [ ] [[plan]] task groups 1–6 complete; scope matches [[requirements]] (stubs only — no
      real LLM/Prophet/SimPy/RAG/React/FastAPI crept in).
- [ ] README updated; PR opened from `phase-2-walking-skeleton` into `main` and green in CI.
