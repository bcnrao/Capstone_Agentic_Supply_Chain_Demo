# Tech Stack

Choices here serve the **capstone MVP** mission (see [[mission]]): breadth,
demonstrability, and reproducibility over production hardening.

## Model strategy: tiered by task

We deliberately split work across two tiers to balance reasoning quality against
cost.

| Tier | Used for | Technology |
|------|----------|------------|
| **Large LLM (reasoning + generation)** | Multi-agent reasoning & orchestration, news/event analysis, mitigation recommendation generation | **Groq `gpt-oss-120b`** (open-weights GPT-OSS 120B, served on Groq for fast, low-cost inference) |
| **Lightweight classifier (execution)** | High-volume, repetitive classification: disruption category, supplier-/lane-level risk scoring | **Fine-tuned DistilBERT** (`distilbert-base-uncased`); low-confidence (<0.5) falls back to a Groq `gpt-oss-120b` zero-shot call |

**Rationale:** the large model is reserved for tasks that genuinely need reasoning and
fluent generation; running it on Groq keeps it fast and cheap. The high-frequency
"execution" classification work still runs on a fine-tuned DistilBERT path — no
generative SLM in the loop — so per-run cost stays low while reasoning quality is
preserved where it matters.

## Where RAG fits (and where it does not)

Real-time news/event analysis is **classification + extraction** on the incoming
article — there is no static corpus to retrieve from, so it is **not** a RAG task.
RAG is applied only where generation genuinely benefits from grounding in a stable
corpus:

- **Impact mapping** — retrieve from an internal **supply-chain knowledge base**
  (suppliers, facilities, trade lanes, commodities) to decide *who/what* an event
  affects. This is the highest-value retrieval step.
- **Mitigation recommendations** — ground the recommendation LLM in **historical
  disruptions + past mitigation playbooks** so advice reflects precedent.
- **Event de-duplication / linking** — retrieve similar recent signals to merge an
  incoming item into an ongoing situation instead of spawning a duplicate alert.

## Vector store / RAG

- **MVP:** **Chroma** — open-source, embeddable, persists to local disk. Runs
  **in-process** under the local `uv` workflow and as a **standalone service** under
  `docker compose` (see Containerization below); either way it persists to a mounted
  volume. Best fit for the always-demoable MVP. (FAISS is a lighter alternative if
  pure similarity search is all that's needed.)
- **Embeddings:** a local **sentence-transformers** model by default (offline /
  cost-friendly — the LLM runs on Groq, so there is no OpenAI dependency), or a hosted
  embeddings API if preferred.
- **Indexed corpora:** internal supply-chain KB (suppliers/lanes/facilities) and a
  historical-disruption / mitigation-playbook corpus.
- **Post-MVP (Phase 12):** swap Chroma for a managed/cloud vector DB (e.g.
  **Pinecone**, or pgvector on managed Postgres) when moving to the cloud.

- API keys via environment variables / `.env` (never committed).
- A thin LLM wrapper module centralizes provider calls so models can be swapped
  without touching agent logic.

## Orchestration

- **LangGraph** — defines the multi-agent graph, state passing, and control flow.
- Shared typed **graph state** object carries signals, classifications, forecasts,
  simulation results, and recommendations between agents.

## Frontend & API layer

The MVP ships **two parallel UIs over one API**, from the MVP stage (not deferred to
production):

- **FastAPI** — a thin API layer that wraps the LangGraph pipeline and exposes it to
  the UIs, giving the React app a stable contract.
- **Gradio** — the fast / internal dashboard, quickest to iterate as agents evolve.
- **React + TypeScript** — the product-facing UI, built against the FastAPI API so the
  front end the product carries forward exists from the MVP.

Both UIs consume the same FastAPI endpoints over the same pipeline/state, so they stay
consistent. Full UX in [[demo-walkthrough]].

## Observability (MVP)

- **Langfuse** (run locally / self-hosted) traces every LangGraph run — node
  inputs/outputs, latency, and token/cost — for debugging and evaluation. It is small and
  pluggable, and fits the local-first MVP.
- Heavier **infra-metrics observability** (Prometheus / Grafana / Loki / OpenTelemetry)
  is a Tier-2 add **on top of** the MVP's Langfuse tracing (see Post-MVP stack).

## Core libraries by agent

| Concern | Library / Tool |
|---------|----------------|
| Ingestion | Multi-source collectors run as a **separate ingestion service** — scheduled poller (APScheduler/cron) for RSS (`feedparser`) + weather (`httpx`), a **FastAPI webhook** (supplier push; synthetic sender in the MVP), a batch loader (historical seed), and on-demand. Normalize + relevance gate + dedupe → **Postgres** (collectors write, `ingest_node` reads new rows). See [[data-ingestion]] |
| Input guardrails | Pydantic schema + relevance / safety gate before the agents — unsafe / off-topic / malformed signals are discarded |
| News & event analysis | **Groq `gpt-oss-120b`** — **classification + extraction** (no RAG; the incoming article is the context) |
| Impact mapping | **RAG** over the internal supply-chain knowledge base — link each event to affected suppliers/lanes/facilities |
| Weather risk | Open-Meteo API client |
| Risk classification | DistilBERT (Hugging Face `transformers`); low-confidence (<0.5) → Groq `gpt-oss-120b` zero-shot fallback |
| Demand forecasting | Facebook **Prophet** |
| Simulation | **SimPy** (discrete-event) + Monte Carlo (NumPy) |
| Mitigation | **Groq `gpt-oss-120b`**, **RAG-grounded** in historical disruptions + mitigation playbooks |
| Output guardrails | Validate the mitigation plan (Pydantic schema · urgency · action count); retry once, then a default plan |
| Dashboard / UI | **Gradio** (fast/internal) + **React + TypeScript** (product-facing), both served by a **FastAPI** API layer wrapping the pipeline |
| Observability | **Langfuse** (local) — traces every LangGraph run (node I/O, latency, token/cost) |
| Evaluation | `scikit-learn` metrics, pandas |

## Data strategy: hybrid (live + cached + synthetic)

To stay realistic *and* reproducible for a graded demo:

- **Live (where free & reliable):** Open-Meteo weather API; Reuters / Supply Chain
  Dive / Google News RSS feeds.
- **Cached:** SupplyChainNet (Kaggle) historical dataset; snapshots of the Freightos
  Baltic Index; saved snapshots of live pulls for offline replay.
- **Synthetic:** AI-generated disruption events / demand shocks to guarantee
  demoable, repeatable scenarios.
- **Graceful fallback:** every live source has a cached/synthetic fallback so a
  failed or rate-limited API never breaks a demo run.
- **Relevance filtering:** live news is gated at ingestion (Stage 0 targeted feeds +
  Stage 1 keyword lexicon) so only supply-chain-relevant signals are stored — the DB
  never fills with irrelevant news. Full design in [[data-ingestion]].

## Storage & data handling

- **pandas** for in-memory tabular work.
- Local persistence for the MVP: a **local PostgreSQL** instance (run via
  `docker compose` or a local install — deliberately **no cloud database**) as the
  system of record for signals and results, plus structured snapshot files
  (CSV/Parquet/JSON) for raw pulls and analytics. Local Postgres is production-shaped
  (so the Tier-2 move to managed Postgres is a connection-string change) yet keeps the
  MVP fully offline.
- Postgres also serves as the **decoupled handoff** between the ingestion service and the
  pipeline: collectors write incoming signals to a signals table and `ingest_node` reads
  only the new rows, so a busy pipeline never blocks ingestion and nothing is lost.
- A defined schema for "disruption signals" shared across agents.

## Language, runtime, tooling

- **Python 3.11+**.
- Dependency management via `requirements.txt` (or `pyproject.toml`).
- `python-dotenv` for config; secrets in `.env`.
- Notebooks acceptable for experiments; agent code lives in importable modules.

## Repository layout

A **monorepo** split by runtime/ecosystem:

- **`backend/`** — the Python service (LangGraph pipeline, ingestion, agents, FastAPI +
  Gradio, notebooks, tests). The `pyproject.toml`/`uv` project lives here; Gradio (a
  Python-rendered UI) stays in `backend/` even though it's a UI, because it runs
  in-process with the pipeline.
- **`frontend/`** — the **React + TypeScript** app (added in Phase 8), alongside
  `backend/`. Reserved for the JS/TS ecosystem so the two toolchains stay separate.
- **Repo root** — shared infrastructure: `docker-compose.yml` (orchestrates the stack)
  and `.env` / `.env.example` (shared config).
- **Where to run what:** run `uv` and `scripts/` commands from **`backend/`**; run
  `docker compose` from the **repo root** (where the compose file and `.env` live).

## Containerization (MVP)

- A minimal **Postgres-only** compose lands **early (Phase 0.5)** so the database exists
  from Phase 1 — data on a named `pgdata` volume, with `pg_dump` snapshots to a gitignored
  repo folder (`data/backups/`). During dev you run just the DB in Docker while the app
  stays on the local `uv` workflow.
- **Docker + docker-compose** — an **additional** way to run the MVP alongside the
  local `uv` workflow (which stays the dev default). The **full** stack (app + Chroma +
  React) is layered onto that same compose at Phase 10 (see [[roadmap]]).
- A `Dockerfile` builds the app image (LangGraph pipeline + FastAPI + Gradio); a
  `docker-compose.yml` orchestrates it as a **multi-service** stack — the app plus a
  standalone **Chroma** service and a **PostgreSQL** service (data on a named volume),
  with the **React** app served as its own container.
- **Volumes** persist the Postgres data, raw snapshots, and the Chroma store across
  restarts; the Postgres connection string and secrets are passed via env / `.env` and
  never baked into images. Everything stays local — no cloud services required.
- `docker compose up` reproduces the full end-to-end demo in containers — useful for
  reviewers and as the on-ramp to the post-MVP cloud deployment.

## Post-MVP stack (Phases 12–13)

These are **not** part of the capstone MVP but are the intended direction once it is
accepted (see [[roadmap]]):

- **Cloud deployment (Phase 12):** build on the Phase 10 Docker setup — harden images
  and run on a cloud host (AWS / GCP / Azure); migrate the **local PostgreSQL** to
  **managed/cloud Postgres** and Chroma to a managed vector DB; add a secrets manager,
  container registry / orchestration (Kubernetes), an Nginx gateway, Redis, and an
  **infra-metrics observability stack** (Prometheus / Grafana / Loki / OpenTelemetry) on
  top of the MVP's Langfuse tracing; basic CI/CD, logging and health checks.
- **Production frontend (Phase 13):** harden the **React** app (already built in the
  MVP) into the **primary** UI with a component library / design system; the
  **FastAPI** backend (also from the MVP) is hardened behind the Nginx gateway. Gradio
  is retired or kept only as an internal debug UI.
- **Priority/severity routing (optional differentiator):** add a conditional branch that
  prioritizes high-severity events (without skipping forecasting) — the MVP pipeline is
  linear.

## Still deferred (beyond current roadmap)

- Message queues (RabbitMQ / Kafka) and multi-tenant auth (JWT / RBAC) — added only if
  scale or multi-tenancy demands them. (Kubernetes, the Nginx gateway, Redis, and the
  observability stack now land in Phase 12; a lightweight local vector store — Chroma —
  *is* in the MVP, with only the at-scale managed version deferred to Phase 12.)
  Revisit only if the project grows past the post-MVP pilot (see [[mission]]
  out-of-scope list).
