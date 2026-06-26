# Phase 2.5 — Dev workflow: interactive notebooks · Requirements

> Roadmap phase: **Phase 2.5 — Dev workflow: interactive notebooks** (see [[roadmap]]).
> Builds on the Phase 2 walking skeleton (the full `ingestion → guardrail → seed →
> classify → impact → forecast → simulate → recommend` graph already runs end-to-end).
> Guidance: [[mission]] (capstone MVP; **demonstrability**; graceful degradation;
> "notebooks acceptable for experiments, agent code lives in importable modules" —
> [[tech-stack]]).

## Goal

Give the **peer group** building Phases 3+ a hands-on way to drive each agent and the
full graph from a notebook, and to onboard quickly. This phase **packages what already
exists** (the `agents/`, `graph/`, and `ingestion/` modules) behind runnable notebooks
with explanatory **Mermaid diagrams** — it adds **no new product capability** and changes
**no** `src/` agent logic.

Notebooks import the **editable `agentic_scd` package**, so they stay in lock-step with
the source and never fork logic.

## Scope decision (confirmed)

- **Setup section — shared & canonical.** One full **Setup** section lives in the
  contributor ("start here") and end-to-end orchestration notebooks: it runs
  `docker compose up -d postgres` (detached, so the kernel isn't blocked), waits for the
  DB healthcheck, then seeds + collects ingestion (`agentic-scd-batch`,
  `agentic-scd-collect`). **Per-agent** notebooks open with a short *"ensure the DB is
  up"* snippet that reuses that setup rather than repeating the whole thing.
- **Git hygiene — commit cleared, no hook.** Notebooks are committed with **outputs
  cleared** (manual discipline; documented in the contributor notebook). No `nbstripout`
  / pre-commit hook this phase. Committed notebooks carry code + markdown (Mermaid
  diagrams) only.
- **Validation — manual run-through checklist.** Success is a documented manual
  walk-through (launch Jupyter, run each notebook top-to-bottom, confirm diagrams render
  and live state shows). No new test deps, no notebook execution in CI — appropriate
  given the notebooks invoke Docker.

### In scope

1. **`notebooks` dependency group** in `pyproject.toml` (`jupyterlab`, `ipykernel`),
   installed via `uv sync --group notebooks` and launched with `uv run jupyter lab`.
   A `notebooks/` directory holds the `.ipynb` files. No change to runtime deps.
2. **End-to-end orchestration notebook** (`notebooks/00_orchestration.ipynb`):
   - Opens with the **overall architecture Mermaid diagram** (its canonical home) so a
     reader grasps the whole flow before running anything.
   - A full **Setup** section: `docker compose up -d postgres` → wait healthy →
     `agentic-scd-batch` + `agentic-scd-collect` → confirm rows in `signals`.
   - Runs the compiled graph (`graph.build_graph()`), **stepping** the pipeline so the
     **state object is inspected after each hop** (classify → impact → forecast →
     simulate → recommend), making the inter-agent handoff visible.
3. **Per-agent notebooks** (one each: `10_classify`, `20_impact`, `30_forecast`,
   `40_simulate`, `50_recommend`). Each:
   - Leads with **its own Mermaid diagram** expanding on that agent — internal steps,
     the input/output **state contract** (which `GraphState` fields it reads vs writes),
     its fallback/degradation path, and a faded upstream/downstream view of where it sits.
   - Has a short *"ensure DB is up"* snippet reusing the shared setup.
   - Constructs a representative input state, calls the **single node in isolation**
     (e.g. `classify_node(state)`), and shows the typed output — the dev surface a peer
     uses to iterate on their agent without the rest of the chain.
4. **Ingestion playground notebook** (`notebooks/60_ingestion.ipynb`): trigger the
   connectors / batch loaders on demand and inspect the `signals` table, the fallback
   path taken, and relevance-gate decisions.
5. **Contributor "start here" notebook** (`notebooks/90_contributor_guide.ipynb`):
   environment / `.env` setup, the canonical **Setup** section, the `notebooks` `uv`
   group, the **clear-outputs-before-commit** convention, and a worked example of
   **plugging a new agent node into the graph** (`agents/<new>.py` + `GraphState`
   channel + `builder.PIPELINE`).
6. **Docs**: a README "Dev notebooks (Phase 2.5)" section pointing peers at
   `uv sync --group notebooks` → `uv run jupyter lab` and the notebook order.
7. **Wrap-up**: mark the roadmap phase complete; PR from `phase-2.5-dev-notebooks` into
   `main`.

### Out of scope — deferred / not this phase

- **Any change to agent logic** in `src/` — this phase only *uses* the existing modules.
  If a notebook needs a seam (e.g. a helper to build a sample state), add a small
  non-breaking helper, not new agent behaviour.
- **`nbstripout` / pre-commit hooks**, **`nbmake`/papermill execution tests**, and
  **notebook execution in CI** — explicitly not adopted (decisions above).
- **Real agent implementations** (Groq/DistilBERT, RAG/Chroma, Prophet, SimPy) — those
  are Phases 3–7; the notebooks run against the current stubs and update naturally as
  each agent deepens behind its unchanged node signature.
- **FastAPI/React/Langfuse** (Phases 8–9).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tooling | **Jupyter `.ipynb`** via a `notebooks` `uv` group (`jupyterlab`, `ipykernel`) | Standard, peers know it; isolated from runtime deps; `.ipynb` renders Mermaid in markdown cells natively. |
| Diagrams | **Mermaid** in markdown cells — overall in the orchestration notebook, per-agent in each agent notebook | Git-friendly (no binary assets), renders in JupyterLab + GitHub; matches the roadmap's "minimal committed outputs". |
| Setup section | **Shared & canonical** (contributor + orchestration); per-agent notebooks reuse via a short "ensure DB up" snippet | Avoids duplicating the Docker/ingest steps across 8 notebooks; one place to maintain. |
| Docker in a cell | `docker compose up -d postgres` **detached** + healthcheck wait | Foreground `up` would block the kernel; detached + poll keeps the notebook flowing. Requires Docker Desktop running (documented prerequisite). |
| Ingestion in a cell | **On-demand** `agentic-scd-collect` + `agentic-scd-batch` (one-shot) | One-shot commands fit a cell; the always-on service (poller/webhook) is long-running and out of scope for the guided run. |
| Git hygiene | **Commit cleared, no hook** | Keeps diffs reasonable without adding tooling; relies on a documented convention. |
| Validation | **Manual run-through checklist** | Notebooks invoke Docker; automated headless execution would need Docker in CI — not worth it for a dev-onboarding aid. |
| Source of truth | Notebooks import the **editable `agentic_scd` package** | Notebooks never re-implement logic; they stay correct as the agents deepen in Phases 3–7. |

## Context & notes

- The whole graph already runs end-to-end (Phase 2): `graph.build_graph()` compiles
  `ingestion → input_guardrail → seed → classify → impact → forecast → simulate →
  recommend`; node fns are importable (`agents.classify.classify_node`, …) and operate on
  the typed `GraphState` (`graph/state.py`). Ingestion CLIs already exist
  (`agentic-scd-collect`, `agentic-scd-batch`) and `docker-compose.yml` defines the
  `postgres` service.
- For per-agent notebooks to call a node in isolation, they build a representative
  `GraphState` (a couple of `DisruptionSignal`s via `SyntheticConnector` + `normalize`,
  or upstream channels for downstream agents). A tiny shared **sample-state helper** may
  be added under `notebooks/` (or `agentic_scd`) to avoid copy-paste — non-breaking.
- Everything stays **local** and offline-capable. The Docker setup is a convenience path;
  where a peer skips it, notebooks should degrade gracefully (the synthetic `seed_node`
  already lets the chain produce a result without real ingested signals).
