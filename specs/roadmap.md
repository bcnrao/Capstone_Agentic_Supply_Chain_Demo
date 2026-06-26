# Roadmap

Sequencing strategy: **foundational ingestion first, then a thin end-to-end slice**
(see [[mission]]). The ingestion layer is the data backbone everything depends on, so
it is built first (Phase 1). Phase 2 then wires every remaining agent as a minimal
stub on top of real signals, giving a runnable, demoable system early; later phases
deepen each agent. Phases are intentionally **small**.

Each phase should end with something runnable and a visible output.

---

## Phase 0 — Project scaffolding ✅ COMPLETE
- Repo structure, `specs/`, Python env, `requirements.txt`, `.env` handling.
- LLM wrapper stub (Groq `gpt-oss-120b`) + config loading.
- Define the shared **disruption-signal schema** and LangGraph **state** object.
- **Done when:** `python` entrypoint runs an empty LangGraph with a stub node.

## Phase 0.5 — Dev data services (Docker Compose for Postgres) ✅ COMPLETE
Postgres is needed from Phase 1 onward (ingestion persists to it), so stand up a
throwaway local DB early — no host install required.
- A root `docker-compose.yml` with a **`postgres`** service (healthcheck; DB name / user /
  password from `.env`). During dev, `docker compose up postgres` runs **just the
  database**; the app keeps running via the local `uv` workflow and connects over the
  `.env` connection string.
- DB data persists in a **named Docker volume** (`pgdata`) — robust on Windows/Docker
  Desktop; survives restarts and rebuilds.
- Small **`pg_dump` / restore scripts** write snapshots to a **gitignored** repo folder
  (`data/backups/`), so seed/demo data is portable and version-able without bind-mounting
  the Postgres data directory.
- The full app + Chroma + React containerization is layered onto **this same compose**
  later (Phase 10).
- **Done when:** `docker compose up postgres` brings up a healthy, volume-persisted
  Postgres the app connects to, and the dump/restore scripts round-trip a snapshot to
  `data/backups/`.

## Phase 1a — Data ingestion layer: core slice ✅ COMPLETE
The foundational data backbone — built first because everything downstream depends on
it. It runs against the Postgres stood up in Phase 0.5. Full design in [[data-ingestion]];
scope/decisions in specs/2026-06-16-data-ingestion.
- Connector/adapter pattern + `sources.yaml` registry (sources toggle by config, not
  code): live **RSS** (`feedparser`, query-scoped), **Open-Meteo** (`httpx`), and a
  **synthetic** generator; each `fetch()` degrades to a cached/synthetic `fallback()` on
  any failure, with the path taken logged.
- Pipeline: fetch → **normalize** → **relevance gate (Stage 0 source targeting +
  Stage 1 keyword lexicon)** → **dedupe** (exact hash) → **persist**.
- Persist to local PostgreSQL — the **decoupled handoff**: collectors write to a `signals`
  table and `ingest_node` reads only the new rows (`status` flag), so a busy pipeline
  never blocks ingestion. Rejected-hash cache + raw snapshot files; idempotent schema init.
- First pipeline node is the **input guardrail** (relevance · Pydantic schema · safety →
  discard unsafe / off-topic). `ingest_node` then emits `new_signals` to graph state.
- Collectors run **on-demand** this slice (`uv run agentic-scd-collect`).
- **Done when:** the on-demand collector yields normalized, relevance-filtered, deduped
  signals persisted to Postgres and read into state, with fallback and the input guardrail
  working. ✅

## Phase 1b — Data ingestion: always-on triggers ✅ COMPLETE
Adds the separate-service trigger machinery deferred from 1a, on the same DB handoff so
1b only adds trigger plumbing — no rework of the core pipeline.
- **Scheduled poller** (APScheduler, in-process) running the enabled connectors
  (RSS + Open-Meteo + synthetic) every N minutes, overlap-safe (`max_instances=1`) and
  toggleable — continuous monitoring even with nobody at the dashboard.
- **FastAPI webhook** for real-time supplier push events (`POST /signals`; synthetic
  sender in the MVP; HMAC signature auth is post-MVP), in the same `agentic-scd-ingest`
  service process as the poller.
- Both triggers write through the **same** normalize → gate → dedupe → persist tail into
  the same `signals` table; graceful with no DB / no network.
- **Done when:** the ingestion service runs continuously (scheduled) and accepts webhook
  pushes — all draining into the same `signals` table the pipeline reads. ✅

## Phase 1c — Data ingestion: batch loaders & retention ✅ COMPLETE
The remaining ingestion sources / housekeeping deferred from 1b.
- **Batch loaders**: cached **Freightos Baltic Index** snapshots + **Kaggle
  SupplyChainNet** historical seed (baselines + KB history). ✅
- Retention/TTL on the seen-rejected cache and accepted signals (Parquet export deferred —
  not selected for this slice). ✅
- **Done when:** a batch run seeds historical baselines into the `signals` table and
  retention/TTL prunes stale rows — without disturbing the live triggers. ✅ (on-demand
  `agentic-scd-batch` CLI; persists, doesn't embed — Chroma stays Phase 4/7)

## Phase 2 — Thin end-to-end slice (walking skeleton) ✅ COMPLETE
With real ingestion in place, wire every **remaining** agent as a minimal stub so the
whole chain runs end-to-end. Each stub does the simplest real thing and passes state
forward.
- Real signals (Phase 1) → classify (rule/keyword stub) → impact-map (hard-coded
  lookup stub) → trivial forecast → tiny simulation → templated recommendation →
  render on Gradio.
- **Done when:** one command runs ingest(real)→classify→impact-map→forecast→simulate→
  recommend→dashboard and shows a result end-to-end. ✅

## Phase 2.5 — Dev workflow: interactive notebooks ✅ COMPLETE
Package the runnable chain behind notebooks so the peer group can drive each agent and
the full graph and develop Phases 3+ in isolation. Adds no product capability.
- A `notebooks/` directory + a `notebooks` `uv` group (`jupyterlab`, `ipykernel`,
  run via `uv run jupyter lab`); notebooks import the editable `agentic_scd` package.
- **End-to-end orchestration**, **per-agent** (classify/impact/forecast/simulate/
  recommend), **ingestion playground**, and a **contributor "start here"** notebook.
- **Diagrams** (Mermaid): an overall architecture diagram in the orchestration notebook,
  and a per-agent diagram in each agent notebook.
- **Docker quick-start** (so Docker is the only prerequisite to clone & run): a `Dockerfile`
  + a second `docker-compose` **`app`** service (Python 3.11 + uv + the project) that comes
  up **idle** alongside Postgres; the user then execs a run mode (CLI / Gradio / Jupyter).
  README gains **With Docker / Without Docker** quick-start sections. This is a **dev
  convenience**; the full multi-service containerization stays **Phase 10**.
- **Done when:** a peer can launch Jupyter and run the end-to-end and per-agent
  notebooks against live state, with diagrams rendering. ✅ (eight notebooks under
  `notebooks/`; `uv sync --group notebooks` → `uv run jupyter lab`; or Docker-only via
  `docker compose up` + `docker compose exec app …`)

## Phase 3 — Risk classification (DistilBERT)
- News & event analysis via Groq `gpt-oss-120b` for category **classification +
  extraction** (no RAG here — the incoming article is the context).
- Fine-tune / apply DistilBERT for disruption-category and supplier-/lane-level
  risk scoring; low-confidence (<0.5) falls back to a Groq `gpt-oss-120b` zero-shot call.
- **Done when:** signals carry real risk categories and numeric risk scores.

## Phase 4 — Impact mapping (RAG + vector store)
- Build the internal **supply-chain knowledge base** (suppliers, facilities, trade
  lanes, commodities) and index it in a **vector store (Chroma)** with embeddings.
- Retrieve over the KB to link each classified event to the affected parts of *our*
  network; attach affected entities to the signal state.
- **Done when:** each event is grounded to concrete suppliers/lanes/facilities it
  impacts, replacing the Phase 1 lookup stub.

## Phase 5 — Demand forecasting (Prophet)
- Prophet baseline forecast on historical demand.
- Fold disruption-risk signals into the forecast (risk-adjusted demand).
- **Done when:** forecast visibly shifts in response to active disruptions.

## Phase 6 — Simulation (SimPy + Monte Carlo)
- Model suppliers/warehouses/ports/retailers as SimPy network nodes.
- Monte Carlo runs → stockout probability and revenue-impact distributions.
- **Done when:** a disruption scenario yields quantified stockout/revenue impact.

## Phase 7 — Mitigation recommendations (RAG-grounded)
- Index a corpus of **historical disruptions + mitigation playbooks** in the vector
  store (reusing the Phase 4 infrastructure).
- Groq `gpt-oss-120b` generates mitigation strategies (alternate suppliers, route
  changes, safety-stock adjustments) grounded via RAG in that corpus plus the
  classification, impact-mapping, and simulation output.
- Add the **output guardrail** (validate the plan — schema · urgency · action count;
  retry once, then a default plan) before results reach the dashboard.
- **Done when:** each high-risk scenario produces actionable, readable
  recommendations that cite relevant precedent and pass the output guardrail.

## Phase 8 — Dashboard, API & alerting (Gradio + React)
- The **`backend/` + `frontend/` repo split** was done ahead of this phase (see
  [[tech-stack]]), so the React app drops into a `frontend/` directory alongside the
  Python `backend/`; Gradio stays in `backend/` (it's a Python-rendered, in-process UI).
- Stand up a **FastAPI** layer that wraps the LangGraph pipeline and exposes it to the
  UIs (a stable contract for the React app).
- Promote the **Gradio** UI from skeleton to real: disruption heatmaps, timelines,
  simulation outcomes, high-risk alerts, scenario exploration.
- Build a **parallel React + TypeScript** app against the FastAPI API, delivering the
  same views product-facing.
- Build the panel layout, run-status strip, and what-if simulation controls described
  in [[demo-walkthrough]] (the canonical UX spec for what the user sees).
- **Done when:** a reviewer can explore risks and run what-if scenarios interactively
  on **both** the Gradio and React UIs, served by FastAPI.

## Phase 9 — Evaluation & tracing
- Classification accuracy, demand-forecast deviation, qualitative simulation /
  recommendation quality checks.
- Instrument every run with a local **Langfuse** service (node inputs/outputs, latency,
  token/cost) for debugging and to back the evaluation.
- **Done when:** a metrics report/panel summarizes system quality and runs are traced in
  Langfuse.

## Phase 10 — Full containerization (Docker)
- **Builds on the Phase 2.5 dev container:** a single idle `app` service + `Dockerfile`
  (Python 3.11 + uv + the project) already exists for the dev quick-start. Phase 10 hardens
  that image and **extends** the compose to the **full** multi-service stack below — it
  does not start from scratch.
- Author a `Dockerfile` for the app (LangGraph pipeline + FastAPI + Gradio) and **extend
  the Phase 0.5 `docker-compose.yml`** to run the full stack — the app container, the
  existing **PostgreSQL** service, a standalone **Chroma** server, and the **React** app
  as its own container.
- Persist the Postgres data (the `pgdata` volume from Phase 0.5), raw snapshots, and the
  Chroma store via mounted **volumes** so data survives restarts; pass the Postgres
  connection string and secrets via env / `.env`, never baked into images. Everything
  stays local — no cloud.
- Docker is an **additional, documented** run path — local `uv` run stays the dev
  default (see [[tech-stack]]).
- **Done when:** `docker compose up` brings up the full system and the end-to-end
  demo runs in containers, matching the local run.

## Phase 11 — Demo polish & docs
- Implement and seed the **Taiwan earthquake → semiconductors** demo scripted in
  [[demo-walkthrough]] (guided single run + interactive what-if), for reproducibility.
- README/run instructions covering **both** the local `uv` and `docker compose` run
  paths; graceful-degradation pass so no live dependency can break the demo.
- **Done when:** a clean, reproducible end-to-end demo runs from documented steps
  (locally and in containers), matching the [[demo-walkthrough]] script.

---

## Beyond MVP

Phases 0–11 complete the capstone MVP (see [[mission]]). The phases below move the
project toward a production-leaning deployment and are explicitly **post-MVP**.

Optional **good-to-have differentiators** (not tied to a single phase) can be layered on
top — e.g. priority/severity conditional routing (prioritize high-severity events without
skipping forecasting), a message queue for ingestion buffering at scale (not for
inter-agent comms — LangGraph state handles that), and JWT/RBAC multi-tenant auth.

## Phase 12 — Cloud deployment
- Build on the Phase 10 Docker setup: harden the images and externalize
  config/secrets for cloud (secrets manager rather than `.env`).
- Migrate the **local PostgreSQL** to **managed/cloud Postgres** and the vector store
  from Chroma to a managed option (e.g. Pinecone or pgvector); run the LangGraph
  backend + FastAPI + UIs on a cloud host (e.g. AWS/GCP/Azure) behind an **Nginx**
  gateway, with **Kubernetes** orchestration, **Redis** caching, and an infra-metrics
  observability stack (Prometheus / Grafana / Loki / OpenTelemetry) on top of the MVP's
  Langfuse tracing.
- Basic CI/CD, logging, and health checks.
- **Done when:** the system runs in the cloud from a clean deploy and is reachable
  via a hosted URL.

## Phase 13 — Production frontend (React)
- Harden the **React** app (already built in the MVP, Phase 8) into the **primary**
  front end against the hardened FastAPI backend.
- Rebuild heatmaps, timelines, simulation views, scenario explorer, and alerts as
  polished React components with a proper design system.
- **Done when:** the React app delivers the full dashboard experience against the
  hosted backend, and Gradio is retired (or kept only as an internal debug UI).

---

### Sequencing notes
- Ingestion (Phase 1) is the foundational data layer and is built first. The walking
  skeleton is Phase 2; after it, phases 3–9 each **deepen one agent** of the
  already-connected chain — integration risk is paid down early.
- Phase 2.5 is a **dev-tooling interlude** (notebooks for the peer group), not an
  agent-deepening step; it adds no product capability and doesn't shift later numbers.
- The **vector store** is introduced in Phase 4 (impact mapping) and **reused** in
  Phase 7 (mitigation) — stand it up once, index two corpora.
- Keep the end-to-end path green after every phase; never let the skeleton rot.
- Phases can be reordered slightly if a data dependency demands it, but ingestion
  (Phase 1) and the thin slice (Phase 2) must come first, in that order. See
  [[tech-stack]] for the tools each phase uses.
- A **Postgres dev compose** lands early (Phase 0.5) so the DB exists from Phase 1;
  **full** containerization (Phase 10) extends that same compose to the whole stack as an
  **additional** run path. Neither replaces the local `uv` workflow, and the cloud phase
  (12) builds on it.
- Phases 12–13 are **post-MVP** and only begin once the capstone demo (Phases 0–11)
  is complete and accepted.
