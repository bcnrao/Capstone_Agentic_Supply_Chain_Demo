# Agentic Supply Chain Disruption Predictor & Simulation Engine

## Project Overview

The Agentic Supply Chain Disruption Predictor & Simulation Engine is an AI-powered platform that proactively detects, analyzes, and predicts supply chain disruptions using a multi-agent architecture.

The system continuously monitors external signals such as news feeds, weather forecasts, freight indices, and logistics events to identify potential risks that may impact suppliers, warehouses, ports, and transportation routes.

Once a disruption is detected, specialized AI agents collaborate to:

- Analyze and classify risks
- Forecast demand and inventory impacts
- Simulate disruption scenarios
- Estimate revenue loss and recovery time
- Generate mitigation recommendations
- Alert stakeholders about high-risk events

The goal is to help organizations move from reactive supply chain management to proactive decision-making through Agentic AI, forecasting, simulation, and Retrieval-Augmented Generation (RAG).

---

## Core Components

### Data Ingestion Agent
Collects and normalizes data from:

- News and RSS feeds
- Weather APIs
- Freight/shipping indices
- Historical supply chain datasets

### Risk Analysis Agent
Identifies:

- Weather risks
- Geopolitical risks
- Logistics disruptions
- Supplier failures
- Demand shocks

### Forecast Agent
Predicts:

- Demand fluctuations
- Inventory shortages
- Lead-time deviations

### Simulation Agent
Runs supply chain simulations to estimate:

- Stockout probability
- Revenue impact
- Time-to-Recovery (TTR)

### Recommendation Agent
Uses RAG to suggest:

- Alternative suppliers
- Alternate shipping routes
- Safety stock adjustments
- Mitigation strategies

### Alert Agent
Generates alerts and summaries for stakeholders.

---

## Technology Stack

### Backend

- Python 3.12
- FastAPI
- LangGraph
- LangChain
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis

### AI / Machine Learning

- OpenAI GPT Models
- HuggingFace Transformers
- DistilBERT
- Prophet
- SimPy
- Pandas
- NumPy
- Scikit-learn

### RAG

- LangChain
- OpenAI Embeddings
- Qdrant Vector Database

### Frontend

- React
- TypeScript
- Vite
- Material UI
- Plotly

### DevOps

- Docker
- Docker Compose
- GitHub Actions

---

## Multi-Agent Workflow

Data Ingestion Agent
↓
Risk Analysis Agent
↓
Forecast Agent + Simulation Agent
↓
Recommendation Agent
↓
Alert Agent

The agents are orchestrated using LangGraph, allowing structured workflows and state management across the entire supply chain risk analysis pipeline.
