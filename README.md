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
(`config/`, `llm/`, `ingestion/`, `graph/`); later phases fill these in per
`specs/roadmap.md`.

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
