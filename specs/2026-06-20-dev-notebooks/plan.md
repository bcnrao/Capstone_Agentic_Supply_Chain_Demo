# Phase 2.5 — Dev workflow: interactive notebooks · Plan

Numbered task groups. Each is independently reviewable; order respects dependencies —
the `uv` group + shared helpers come before the notebooks that use them, the canonical
setup is authored before the per-agent notebooks that reuse it, and docs/wrap-up come
last. Scope and decisions in [[requirements]]; success criteria in [[validation]].

This phase **does not modify agent logic** in `src/` — it packages the existing modules
behind notebooks. Any `src/` addition is limited to a small, non-breaking helper.

---

## 1. Notebook dependency group & scaffolding
1.1 Add a `[dependency-groups]` **`notebooks`** group to `pyproject.toml`
    (`jupyterlab`, `ipykernel`); `uv lock`. Confirm `uv sync --group notebooks` and
    `uv run jupyter lab` work, and that the project's venv is selectable as a kernel.
1.2 Create the `notebooks/` directory with the agreed filenames
    (`00_orchestration`, `10_classify`, `20_impact`, `30_forecast`, `40_simulate`,
    `50_recommend`, `60_ingestion`, `90_contributor_guide`).
1.3 *(Optional, non-breaking)* a small **sample-state helper** (e.g.
    `notebooks/_helpers.py` or `agentic_scd.devtools`) that builds a representative
    `GraphState` / a few `DisruptionSignal`s (via `SyntheticConnector` + `normalize`) so
    per-agent notebooks don't copy-paste fixtures. Reused, not duplicated.

## 2. Canonical Setup section (DB + ingestion)
2.1 Author the reusable **Setup** cells (in the contributor + orchestration notebooks):
    - `!docker compose up -d postgres` (detached), then a **healthcheck-wait** cell
      (`docker compose ps` or a `psycopg` connect-retry loop) that blocks until the DB is
      ready, with a clear message if Docker isn't running.
    - `!uv run agentic-scd-batch` (historical seed) and `!uv run agentic-scd-collect`
      (live/synthetic) — one-shot.
    - A confirm cell: query/print the `signals` row count so the peer sees data landed.
2.2 The short **"ensure DB is up"** snippet for per-agent notebooks: a guarded check that
    Postgres is reachable, pointing back to the orchestration/contributor Setup if not
    (degrade gracefully — the synthetic `seed_node` still yields a result without a DB).

## 3. End-to-end orchestration notebook (`00_orchestration.ipynb`)
3.1 Opening markdown cell: the **overall architecture Mermaid diagram** (its canonical
    home) — ingestion service → Postgres handoff → graph (`ingestion → guardrail → seed →
    classify → impact → forecast → simulate → recommend`) → render.
3.2 The canonical **Setup** section (from group 2).
3.3 **Stepped run**: build the graph (`graph.build_graph()`) and walk the pipeline so the
    **`GraphState` is inspected after each hop** — print/pretty-show `new_signals`, then
    `classifications`, `impacts`, `forecast`, `simulation`, `recommendation` as they
    populate, with a one-line note on what each agent just did.

## 4. Per-agent notebooks (`10`–`50`)
For each agent (classify, impact, forecast, simulate, recommend):
4.1 Opening **Mermaid diagram** expanding on the agent — internal steps, the
    input/output **state contract** (fields read vs written), its fallback/degradation
    path, and a faded upstream/downstream view.
4.2 The short **"ensure DB is up"** snippet (group 2.2).
4.3 Build a representative input state (sample-state helper or upstream channels), call
    the **single node in isolation** (`<agent>_node(state)`), and display the typed
    output; a short markdown note on how a peer extends this agent in its Phase (3–7).

## 5. Ingestion playground (`60_ingestion.ipynb`)
5.1 Trigger connectors / batch loaders on demand (`agentic-scd-collect`,
    `agentic-scd-batch`, or the connector classes directly) and **inspect the `signals`
    table** (recent rows, source, status).
5.2 Show the **fallback path taken** (live → cached/synthetic) and **relevance-gate**
    decisions (kept vs rejected, with reason), so peers understand what reaches the graph.

## 6. Contributor "start here" notebook (`90_contributor_guide.ipynb`)
6.1 Onboarding: `.env` setup, `uv sync --group notebooks`, `uv run jupyter lab`, selecting
    the kernel, and the recommended **notebook reading order**.
6.2 The canonical **Setup** section (shared with orchestration).
6.3 The **clear-outputs-before-commit** convention (Cell → All Output → Clear, or
    `jupyter nbconvert --clear-output`), stated as the repo norm for notebooks.
6.4 A worked example of **adding a new agent to the graph**: new `agents/<name>.py`
    `*_node`, a `GraphState` channel, and inserting it into `builder.PIPELINE` — the path
    a peer follows to land their Phase-3+ module.

## 7. Docs & wrap-up
7.1 README **"Dev notebooks (Phase 2.5)"** section: the `uv` group, `jupyter lab`, the
    notebook list/order, the Docker-Desktop prerequisite, and the clear-outputs norm.
7.2 Run the full **manual run-through checklist** in [[validation]]; **clear all notebook
    outputs**; mark the Phase 2.5 roadmap entry complete (✅).
7.3 Open a PR from `phase-2.5-dev-notebooks` into `main`.
