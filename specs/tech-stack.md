# Tech Stack

Choices here serve the **capstone POC** mission (see [[mission]]): breadth,
demonstrability, and reproducibility over production hardening.

## Model strategy: tiered by task

We deliberately split work across two tiers to balance reasoning quality against
cost.

| Tier | Used for | Technology |
|------|----------|------------|
| **Large LLM (reasoning + generation)** | Multi-agent reasoning & orchestration, news/event analysis, mitigation recommendation generation | **OpenAI** large model (e.g. `gpt-4o` / `gpt-4.1` class) |
| **Lightweight classifier (execution)** | High-volume, repetitive classification: disruption category, supplier-/lane-level risk scoring | **Fine-tuned DistilBERT** (`distilbert-base-uncased`) |

**Rationale:** the expensive large model is reserved for tasks that genuinely need
reasoning and fluent generation. The high-frequency "execution" classification work
runs on a cheap, fast, fine-tuned DistilBERT path — no generative SLM in the loop.
This keeps per-run cost low while preserving reasoning quality where it matters.

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

- **POC:** **Chroma** — open-source, embeddable (runs in-process), persists to local
  disk, no separate service to operate. Best fit for the always-demoable POC.
  (FAISS is a lighter alternative if pure similarity search is all that's needed.)
- **Embeddings:** OpenAI embeddings, or a local sentence-transformers model to keep
  cost/offline-friendliness.
- **Indexed corpora:** internal supply-chain KB (suppliers/lanes/facilities) and a
  historical-disruption / mitigation-playbook corpus.
- **Post-POC (Phase 11):** swap Chroma for a managed/cloud vector DB (e.g.
  **Pinecone**, or pgvector on managed Postgres) when moving to the cloud.

- API keys via environment variables / `.env` (never committed).
- A thin LLM wrapper module centralizes provider calls so models can be swapped
  without touching agent logic.

## Orchestration

- **LangGraph** — defines the multi-agent graph, state passing, and control flow.
- Shared typed **graph state** object carries signals, classifications, forecasts,
  simulation results, and recommendations between agents.

## Core libraries by agent

| Concern | Library / Tool |
|---------|----------------|
| Ingestion | `feedparser` (RSS), `httpx` (APIs), normalize + keyword relevance gate + dedupe — see [[data-ingestion]] |
| News & event analysis | OpenAI large LLM — **classification + extraction** (no RAG; the incoming article is the context) |
| Impact mapping | **RAG** over the internal supply-chain knowledge base — link each event to affected suppliers/lanes/facilities |
| Weather risk | Open-Meteo API client |
| Risk classification | DistilBERT (Hugging Face `transformers`) |
| Demand forecasting | Facebook **Prophet** |
| Simulation | **SimPy** (discrete-event) + Monte Carlo (NumPy) |
| Mitigation | OpenAI large LLM, **RAG-grounded** in historical disruptions + mitigation playbooks |
| Dashboard | **Gradio** |
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
- Lightweight local persistence for the POC: structured files (CSV/Parquet/JSON)
  and/or **SQLite** for signals and results — no heavyweight DB.
- A defined schema for "disruption signals" shared across agents.

## Language, runtime, tooling

- **Python 3.11+**.
- Dependency management via `requirements.txt` (or `pyproject.toml`).
- `python-dotenv` for config; secrets in `.env`.
- Notebooks acceptable for experiments; agent code lives in importable modules.

## Post-POC stack (Phases 11–12)

These are **not** part of the capstone POC but are the intended direction once it is
accepted (see [[roadmap]]):

- **Cloud deployment (Phase 11):** Docker containers; a cloud host (AWS / GCP /
  Azure); managed persistence (e.g. managed Postgres) replacing local SQLite;
  secrets manager; basic CI/CD, logging, and health checks; scheduled/triggered
  ingestion.
- **Production frontend (Phase 12):** a **React** single-page app (with a component
  library / design system) replacing Gradio, talking to the agent pipeline through a
  **FastAPI** backend API. Gradio is retired or kept only as an internal debug UI.

## Still deferred (beyond current roadmap)

- Managed/large-scale vector DB, message queues, full container orchestration (e.g.
  Kubernetes), multi-tenant auth, and a full observability stack. (A lightweight
  local vector store — Chroma — *is* in the POC; only the at-scale managed version
  is deferred.) Revisit only if the project grows past the post-POC pilot (see
  [[mission]] out-of-scope list).
