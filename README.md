# Agentic Supply Chain Disruption Predictor & Simulation Engine

An AI-powered supply chain disruption prediction and simulation system that proactively
monitors global risk signals, predicts potential supply chain disruptions, forecasts demand
impact, and simulates mitigation scenarios using multi-agent AI workflows, Retrieval-Augmented
Generation (RAG), time-series forecasting, and discrete-event simulation techniques.

## Overview

Modern supply chains are highly interconnected networks involving suppliers, manufacturers,
logistics providers, ports, warehouses, and retailers across multiple countries. Disruptions
such as extreme weather events, geopolitical conflicts, labor strikes, port closures, tariffs,
or factory shutdowns can significantly affect inventory availability, delivery timelines, and
revenue.

Most organizations react only *after* disruptions occur because monitoring large-scale,
real-time data sources manually is difficult and inefficient. This project builds a
**LangGraph-orchestrated multi-agent platform** that continuously ingests disruption-related
information, classifies supply chain risks, forecasts demand fluctuations, simulates disruption
scenarios, and generates mitigation recommendations.

The platform aims to support proactive risk management, improve operational resilience, and
assist organizations in strategic supply chain planning.

## Key Features

- **Real-time risk monitoring** across news feeds, weather alerts, shipping indices, and logistics signals
- **LLM-based disruption classification** (weather, geopolitical, logistics, raw material shortages, demand shocks)
- **Weather risk detection** for ports, transport hubs, and manufacturing facilities
- **Supplier-level and trade-lane risk scoring** via DistilBERT classifiers
- **Demand forecasting** that incorporates disruption risk signals
- **Discrete-event simulation** of supply chain networks with Monte Carlo stockout/revenue impact estimation
- **Natural-language mitigation recommendations** (alternate suppliers, route changes, safety stock adjustments)
- **Interactive dashboard** with disruption heatmaps, timelines, simulation outcomes, and high-risk alerts

## Architecture: Multi-Agent Workflow

The system is composed of specialized agents orchestrated with LangGraph:

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | **Real-Time Data Ingestion Agent** | Continuously collects data from RSS feeds, logistics/weather APIs, and shipping indices; extracts disruption events using `feedparser` and NLP pipelines; stores signals in a structured format |
| 2 | **News & Event Analysis Agent** | Analyzes news articles and logistics alerts with LLMs; identifies disruption categories |
| 3 | **Weather Risk Monitoring Agent** | Fetches forecasts via Open-Meteo API; detects extreme weather affecting ports, hubs, and factories |
| 4 | **Risk Classification Agent** | LangGraph-based orchestration using DistilBERT classifiers; generates supplier-level and trade-lane risk scores |
| 5 | **Demand Forecasting Agent** | Trains forecasting models with Facebook Prophet; folds disruption signals into demand predictions |
| 6 | **Simulation Agent** | Models suppliers, warehouses, ports, and retailers as network nodes using SimPy discrete-event simulation; runs Monte Carlo simulations for stockout probability and revenue impact |
| 7 | **Mitigation Recommendation Agent** | Generates natural-language mitigation strategies using LLMs |
| 8 | **Dashboard & Alerting** | Gradio dashboard for risk visualization, scenario analysis, and high-risk alerts |
| 9 | **Evaluation** | Measures risk classification accuracy, demand forecast deviation, and simulation/recommendation quality |

## Data Sources

| Source | Type | Content |
|--------|------|---------|
| [SupplyChainNet (Kaggle)](https://www.kaggle.com/datasets) | Dataset | Historical supply chain transactions, shipping records, supplier info, logistics delays, disruption events |
| [Freightos Baltic Index](https://fbx.freightos.com/) | Public index | Container shipping rate indices, freight trends, logistics cost fluctuations |
| [Open-Meteo API](https://open-meteo.com/) | API | Historical and forecast weather data for logistics hubs and shipping regions |
| Reuters / Bloomberg / Supply Chain Dive RSS, Google News API | News/RSS | Articles on labor strikes, geopolitical risks, tariffs, factory shutdowns, logistics disruptions |
| AI-generated synthetic events | Synthetic | Simulated demand shocks, disruption narratives, supplier failures, logistics incidents |

## Tech Stack

- **Orchestration:** LangGraph (multi-agent workflows)
- **LLMs / RAG:** News analysis & mitigation recommendation generation
- **Classification:** DistilBERT (`distilbert-base-uncased`)
- **Forecasting:** Facebook Prophet
- **Simulation:** SimPy (discrete-event), Monte Carlo methods
- **Ingestion:** feedparser, NLP pipelines
- **Dashboard:** Gradio

## Getting Started (Phase 0 scaffold)

The repository currently contains the **Phase 0 scaffold**: an importable
`agentic_scd` package, a thin LLM wrapper, the shared `DisruptionSignal` schema,
a typed LangGraph state, and a single stub ingestion node wired into a runnable
graph. It runs **fully offline** with no API key.

**Prerequisites:** [`uv`](https://docs.astral.sh/uv/) (it provisions Python 3.11+
automatically).

```bash
uv sync                       # create .venv + install from pyproject.toml + uv.lock
uv run agentic-scd            # build & run the graph; prints a GraphState with new_signals
#   python -m agentic_scd     # equivalent module invocation
uv run pytest                 # smoke test
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
```

Configuration is read from a `.env` file (see `.env.example`). With no
`GROQ_API_KEY` set, the LLM wrapper returns a deterministic mock response so the
scaffold never requires network access. Package layout lives under `src/agentic_scd/`
(`config/`, `llm/`, `ingestion/`, `graph/`, `db/`); later phases fill these in per
`specs/roadmap.md`.

## Dev database (Phase 0.5)

A throwaway **local Postgres** runs via Docker Compose so a database exists from
Phase 1 onward. The app still runs on the local `uv` workflow and connects over
`DATABASE_URL` — Docker here runs **only** the database (no tables/schema yet;
those land in Phase 1). **Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/)
running.**

```bash
docker compose up -d postgres     # start just the DB (postgres:16-alpine)
docker compose ps                 # postgres should report "healthy"
```

The connection settings come from `.env` (`POSTGRES_*` feed the container;
`DATABASE_URL` is what the app uses). Verify connectivity:

```bash
uv run python -c "from agentic_scd.db import ping; print(ping())"
#   PingResult(ok=True, detail='SELECT 1 ok')  when the DB is up
```

If no database is reachable, `ping()` returns `PingResult(ok=False, ...)` with a
clear message (never a crash), so the app stays offline-runnable and the test
suite still passes.

**Backup / restore** (cross-platform, via `uv run`). Dumps are timestamped SQL
files written to `data/backups/` (git-ignored):

```bash
uv run python scripts/db_dump.py                       # -> data/backups/pgdump-<ts>.sql
uv run python scripts/db_restore.py data/backups/<snapshot>.sql
```

Data persists on the named `pgdata` volume across `docker compose down` → `up`;
`docker compose down -v` also drops the volume (wiping the data).

## Data ingestion (Phase 1)

The ingestion layer turns messy external data into clean, deduplicated, **relevant**
disruption signals. Collectors run **on-demand** (the scheduled poller and webhook are
Phase 1b) through one pipeline: **fetch → normalize → relevance-gate → dedupe →
persist**. The graph then reads what was persisted.

```bash
docker compose up -d postgres     # Phase 0.5 DB (optional — see offline note below)
uv run agentic-scd-collect        # run every enabled source once through the pipeline
```

The collector prints a per-source summary (fetched / kept / dropped / persisted /
live-vs-fallback), e.g.:

```
source                fetched   kept  dropped  persisted       path
supplychain_rss           510    469       41        469       live
open_meteo                  3      3        0          3       live
synthetic                   3      3        0          3       live
```

**Sources** are toggled by config in `sources.yaml` (not code): query-scoped RSS
(`feedparser`), Open-Meteo weather (`httpx`), and an always-available synthetic
generator. Each connector's `fetch()` is wrapped so any failure (network / empty)
degrades to a cached/synthetic `fallback()` instead of crashing — the path taken is
logged.

**Relevance gate** (Stage 0 + Stage 1 only): Stage 0 targets supply-chain sources;
Stage 1 keeps a signal only if its normalized text hits the disruption lexicon in
`lexicon.yaml` (strike, embargo, typhoon, tariff, …). It favors recall and logs the
drop rate; re-tune the lexicon and re-run freely.

**What persists where:**
- **Accepted signals** (full record + `raw_payload`, `status='new'`) → Postgres
  `signals` table (the system of record and the decoupled handoff).
- **Rejected items** → only their `dedup_hash` in `seen_rejected` (so the same junk
  isn't re-evaluated every run).
- **Raw pulls** → timestamped JSON **snapshot files** in `data/snapshots/`
  (gitignored), *not* the DB — the audit/replay path. Offline fallback fixtures live
  under `data/fallback/` (committed).

Dedupe is **exact SHA-256** over the normalized title+body, so re-running the collector
never creates duplicate rows.

**Into the graph.** `uv run agentic-scd` runs the pipeline: `ingest_node` drains only
`status='new'` rows (flipping them to `processing`, so old news is never reprocessed),
then an **input guardrail** node discards anything off-topic / unsafe / schema-invalid
before downstream agents.

**Offline contract.** Everything runs with **no Docker and no network**: the synthetic
connector and cached fallbacks still yield signals, and with no DB the collector reports
in-memory only while `ingest_node` returns an empty batch — never a crash.

```bash
uv run agentic-scd-collect        # synthetic + cached fallbacks, no crash
uv run agentic-scd                # graph runs end-to-end
uv run pytest                     # green; DB-touching tests skip cleanly when no DB
```

## Evaluation

- Risk classification accuracy
- Demand forecast deviation
- Simulation realism and mitigation recommendation quality

## Challenges

1. **Real-Time Data Integration** — continuously process multiple external data sources reliably
2. **Risk Signal Extraction** — identify meaningful disruption indicators from noisy news and weather data
3. **Forecasting Uncertainty** — handle uncertainty in demand forecasting under disruption conditions
4. **Simulation Complexity** — model realistic supply chain behavior and interconnected dependencies
5. **Multi-Agent Coordination** — synchronize ingestion, forecasting, simulation, and mitigation agents
6. **Scalability** — efficiently manage large-scale supplier networks and logistics data
7. **Recommendation Reliability** — generate actionable, business-relevant mitigation strategies

## References

- [Facebook Prophet Documentation](https://facebook.github.io/prophet/)
- [SimPy Documentation](https://simpy.readthedocs.io/en/latest/)
- [Feedparser Documentation](https://feedparser.readthedocs.io/en/latest/)
- [DistilBERT Model Documentation](https://huggingface.co/distilbert-base-uncased)
- [Open-Meteo API](https://open-meteo.com/)
- [Freightos Baltic Index](https://fbx.freightos.com/)

---

*Capstone Project — IISc / TalentSprint (Part of Accenture).*
