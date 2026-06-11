# Roadmap

Sequencing strategy: **foundational ingestion first, then a thin end-to-end slice**
(see [[mission]]). The ingestion layer is the data backbone everything depends on, so
it is built first (Phase 1). Phase 2 then wires every remaining agent as a minimal
stub on top of real signals, giving a runnable, demoable system early; later phases
deepen each agent. Phases are intentionally **small**.

Each phase should end with something runnable and a visible output.

---

## Phase 0 — Project scaffolding
- Repo structure, `specs/`, Python env, `requirements.txt`, `.env` handling.
- LLM wrapper stub (OpenAI large model) + config loading.
- Define the shared **disruption-signal schema** and LangGraph **state** object.
- **Done when:** `python` entrypoint runs an empty LangGraph with a stub node.

## Phase 1 — Data ingestion layer (foundation)
The foundational data backbone — built first because everything downstream depends on
it. Full design in [[data-ingestion]].
- Connector/adapter pattern + `sources.yaml` registry: RSS (`feedparser`), Open-Meteo
  (`httpx`), cached Freightos snapshots, Kaggle dataset loader, synthetic generator.
- Pipeline: fetch → **normalize** → **relevance gate (Stage 0 source targeting +
  Stage 1 keyword lexicon)** → **dedupe** (exact hash) → **persist** → **emit**.
- Persist to SQLite (system of record) + rejected-hash cache + raw snapshot files;
  graceful fallback to cached/synthetic on any source failure.
- Expose as a single LangGraph node emitting `new_signals` to graph state.
- **Done when:** running ingestion yields normalized, relevance-filtered, deduped
  signals persisted to the DB and emitted to state — from live, cached, and synthetic
  sources, with fallback working.

## Phase 2 — Thin end-to-end slice (walking skeleton)
With real ingestion in place, wire every **remaining** agent as a minimal stub so the
whole chain runs end-to-end. Each stub does the simplest real thing and passes state
forward.
- Real signals (Phase 1) → classify (rule/keyword stub) → impact-map (hard-coded
  lookup stub) → trivial forecast → tiny simulation → templated recommendation →
  render on Gradio.
- **Done when:** one command runs ingest(real)→classify→impact-map→forecast→simulate→
  recommend→dashboard and shows a result end-to-end.

## Phase 3 — Risk classification (DistilBERT)
- News & event analysis via OpenAI large LLM for category **classification +
  extraction** (no RAG here — the incoming article is the context).
- Fine-tune / apply DistilBERT for disruption-category and supplier-/lane-level
  risk scoring.
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
- OpenAI large LLM generates mitigation strategies (alternate suppliers, route
  changes, safety-stock adjustments) grounded via RAG in that corpus plus the
  classification, impact-mapping, and simulation output.
- **Done when:** each high-risk scenario produces actionable, readable
  recommendations that cite relevant precedent.

## Phase 8 — Dashboard & alerting
- Promote Gradio UI from skeleton to real: disruption heatmaps, timelines,
  simulation outcomes, high-risk alerts, scenario exploration.
- **Done when:** a reviewer can explore risks and run what-if scenarios interactively.

## Phase 9 — Evaluation
- Classification accuracy, demand-forecast deviation, qualitative simulation /
  recommendation quality checks.
- **Done when:** a metrics report/panel summarizes system quality.

## Phase 10 — Demo polish & docs
- Curated demo scenario(s), seeded for reproducibility; README/run instructions;
  graceful-degradation pass so no live dependency can break the demo.
- **Done when:** a clean, reproducible end-to-end demo runs from documented steps.

---

## Beyond POC

Phases 0–10 complete the capstone POC (see [[mission]]). The phases below move the
project toward a production-leaning deployment and are explicitly **post-POC**.

## Phase 11 — Cloud deployment
- Containerize the system (Docker); externalize config/secrets for cloud.
- Stand up managed persistence and run the LangGraph backend + dashboard on a cloud
  host (e.g. AWS/GCP/Azure); migrate the vector store from Chroma to a managed
  option (e.g. Pinecone or pgvector); add scheduled/triggered ingestion.
- Basic CI/CD, logging, and health checks.
- **Done when:** the system runs in the cloud from a clean deploy and is reachable
  via a hosted URL.

## Phase 12 — Production frontend (React)
- Replace the Gradio dashboard with a dedicated **React** front end consuming a
  backend API (the agent pipeline exposed via FastAPI).
- Rebuild heatmaps, timelines, simulation views, scenario explorer, and alerts as
  React components with a proper design system.
- **Done when:** the React app delivers the full dashboard experience against the
  hosted backend, and Gradio is retired (or kept only as an internal debug UI).

---

### Sequencing notes
- Ingestion (Phase 1) is the foundational data layer and is built first. The walking
  skeleton is Phase 2; after it, phases 3–9 each **deepen one agent** of the
  already-connected chain — integration risk is paid down early.
- The **vector store** is introduced in Phase 4 (impact mapping) and **reused** in
  Phase 7 (mitigation) — stand it up once, index two corpora.
- Keep the end-to-end path green after every phase; never let the skeleton rot.
- Phases can be reordered slightly if a data dependency demands it, but ingestion
  (Phase 1) and the thin slice (Phase 2) must come first, in that order. See
  [[tech-stack]] for the tools each phase uses.
- Phases 11–12 are **post-POC** and only begin once the capstone demo (Phases 0–10)
  is complete and accepted.
