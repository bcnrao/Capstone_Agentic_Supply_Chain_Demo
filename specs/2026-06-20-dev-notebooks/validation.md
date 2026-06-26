# Phase 2.5 — Dev workflow: interactive notebooks · Validation

How to know the implementation succeeded and the branch can merge. Maps to the task
groups in [[plan]] and the scope in [[requirements]]. The roadmap "Done when" is the north
star: **a peer can launch Jupyter and run the end-to-end and per-agent notebooks against
live state, with diagrams rendering.**

Validation here is a **manual run-through checklist** (confirmed decision) — the notebooks
invoke Docker, so there is no automated notebook execution in CI this phase.

## Acceptance criteria

### A. Environment & scaffolding
- [ ] `uv sync --group notebooks` installs `jupyterlab` + `ipykernel`; **runtime deps are
      unchanged** (no new entries outside the `notebooks` group; `uv.lock` updated).
- [ ] `uv run jupyter lab` launches and the project venv is selectable as the kernel.
- [ ] `notebooks/` contains the eight notebooks (`00_orchestration`, `10_classify`,
      `20_impact`, `30_forecast`, `40_simulate`, `50_recommend`, `60_ingestion`,
      `90_contributor_guide`).
- [ ] **No agent logic in `src/` changed** — `git diff main -- src/agentic_scd/agents
      src/agentic_scd/graph` shows no behavioural change (at most a small, non-breaking
      sample-state helper). Existing `uv run pytest` still passes.

### B. Setup section (DB + ingestion, from a notebook)
- [ ] In the orchestration (and contributor) notebook, the Setup cells run
      `docker compose up -d postgres`, **wait for the DB to be healthy**, then
      `agentic-scd-batch` + `agentic-scd-collect`, and a confirm cell shows a **non-zero
      `signals` row count**.
- [ ] The Docker cell is **detached** (does not hang the kernel); if Docker isn't running,
      the wait cell prints a clear, actionable message instead of hanging.
- [ ] Per-agent notebooks' **"ensure DB is up"** snippet works whether or not the DB is
      up — it either proceeds or degrades gracefully (synthetic state), never hangs.

### C. Diagrams render
- [ ] The **orchestration notebook** opens with the **overall architecture** Mermaid
      diagram and it **renders** in JupyterLab (and on GitHub).
- [ ] **Each per-agent notebook** opens with its **own** Mermaid diagram showing internal
      steps, the input/output state contract, the fallback path, and upstream/downstream
      context — and it renders.

### D. Notebooks run end-to-end (manual)
- [ ] **Orchestration**: runs top-to-bottom and shows the **`GraphState` after each hop**
      (`new_signals` → `classifications` → `impacts` → `forecast` → `simulation` →
      `recommendation`), each populated and typed.
- [ ] **Each per-agent notebook**: builds a representative state, calls the single node in
      isolation (`<agent>_node(state)`), and displays sensible typed output.
- [ ] **Ingestion playground**: triggers a collect/batch, shows recent `signals` rows, the
      fallback path taken, and relevance-gate (kept/rejected) decisions.
- [ ] **Contributor guide**: a new peer can follow it from a cold start (env → `uv sync
      --group notebooks` → Jupyter → Setup) and reach a populated state; the "add a new
      agent to the graph" worked example is accurate against current `builder.PIPELINE`.

### E. Git hygiene & docs
- [ ] All committed notebooks have **outputs cleared** (no execution outputs / counts in
      the `.ipynb` JSON); the clear-before-commit convention is documented in the
      contributor notebook and README.
- [ ] README has a **"Dev notebooks (Phase 2.5)"** section (uv group, `jupyter lab`,
      notebook order, Docker-Desktop prerequisite, clear-outputs norm).
- [ ] No `nbstripout`/pre-commit hook and no `nbmake`/papermill deps were added (out of
      scope this phase).

## Manual smoke test

```bash
# 1. Install the notebook tooling and launch Jupyter
uv sync --group notebooks
uv run jupyter lab

# 2. In JupyterLab, run in order and watch for the checks above:
#    90_contributor_guide  -> onboarding + Setup (docker up, seed, collect) succeeds
#    00_orchestration      -> arch diagram renders; stepped run shows state after each hop
#    10..50_<agent>        -> agent diagram renders; node called in isolation shows output
#    60_ingestion          -> signals rows, fallback path, relevance-gate decisions

# 3. Before committing: clear all outputs
uv run jupyter nbconvert --clear-output --inplace notebooks/*.ipynb
```

Expected: every notebook runs top-to-bottom without uncaught errors; with Docker Desktop
running, Setup lands real signals and the orchestration run flows them through the graph;
without Docker, notebooks degrade gracefully (synthetic seed) rather than hanging.

## Definition of done
- [ ] All acceptance criteria (A–E) checked.
- [ ] [[plan]] task groups 1–7 complete; scope matches [[requirements]] (notebooks only —
      no agent-logic changes, no `nbstripout`/`nbmake`/CI execution crept in).
- [ ] Notebook outputs cleared; README updated; Phase 2.5 marked complete in [[roadmap]].
- [ ] PR opened from `phase-2.5-dev-notebooks` into `main` and green in CI (existing
      test suite unaffected).
