# Mission

## What we are building

An **Agentic Supply Chain Disruption Predictor & Simulation Engine**: a
LangGraph-orchestrated, multi-agent system that proactively monitors global risk
signals, classifies supply chain disruptions, forecasts demand impact, simulates
mitigation scenarios, and produces natural-language recommendations.

## Why

Most organizations react *after* a disruption hits because monitoring large-scale,
real-time signals by hand is slow and error-prone. The mission is to shift teams
from **reactive** to **proactive** risk management by turning noisy external
signals (news, weather, freight indices, logistics data) into ranked risks,
quantified impact estimates, and actionable mitigation options.

## Scope: Capstone Demo / Minimum Viable Product (MVP)

This is a **capstone MVP**, not a production system. That choice drives every
trade-off below.

**Optimize for:**
- **Breadth** — a working end-to-end path through all seven agents that proves the
  multi-agent concept.
- **Demonstrability** — every run produces a clear, reproducible story a reviewer
  can follow on a dashboard.
- **Reproducibility** — demos must not break because an external API is down or
  rate-limited (see [[tech-stack]] data strategy).

**In scope for the MVP (infrastructure):**
- **Local PostgreSQL** — a local Postgres instance (via `docker compose` or a local
  install, **never a cloud database**) is the system of record, so the MVP is
  production-shaped yet runs fully offline (see [[tech-stack]]).
- **Continuous multi-source ingestion** — a **separate ingestion service** (scheduled
  poller + supplier webhook + batch loader + on-demand) writes to a Postgres handoff, so
  the system monitors continuously rather than only on demand (see [[data-ingestion]]).
- **Guardrails** — input and output guardrail gates bracket the pipeline: drop
  unsafe/irrelevant signals on the way in, and validate recommendations before they
  reach the dashboard.
- **Parallel React UI + FastAPI** — alongside the Gradio dashboard, a React app
  (served by a FastAPI layer that wraps the pipeline) is built from the MVP stage, so
  the product-facing front end exists early (see [[tech-stack]], [[demo-walkthrough]]).
- **Local observability** — a local **Langfuse** service traces every run (node
  inputs/outputs, latency, token/cost) for debugging and evaluation.
- **Local containerization** — a Postgres dev compose lands early (Phase 0.5) so the DB
  exists from Phase 1; the full stack is runnable via `docker compose` (Phase 10) as an
  additional path alongside the local `uv` workflow (see [[roadmap]]).

**Explicitly out of scope for the MVP (Phases 0–11):**
- Production hardening: HA, autoscaling, multi-tenant security, SLAs.
- Live trading/ERP integrations or write-back into real procurement systems.
- Real-money decisions — output is decision *support*, not automated action.

**Planned post-MVP (Phases 12–13, see [[roadmap]]):**
- **Cloud deployment** — host the containerized backend + dashboards on a managed
  cloud platform, migrating the local Postgres to managed persistence, plus a secrets
  manager and CI/CD.
- **Production frontend** — harden the React app (already built in the MVP) into the
  primary UI and retire the Gradio dashboard, or keep it only as an internal debug
  surface.

These post-MVP phases begin only once the capstone demo is complete and accepted;
they shift the project from "always-demoable MVP" toward a production-leaning pilot.

## Primary users

- **Supply chain / risk analysts** — see ranked risks and simulated impact, explore
  "what-if" mitigations.
- **Operations & planning leads** — consume high-level alerts and recommended
  actions.
- **Capstone reviewers** — evaluate the system end-to-end against the metrics below.

## Success criteria

A successful MVP can, in a single demo run:

1. Ingest disruption signals from a mix of live, cached, and synthetic sources via
   scheduled, webhook, and on-demand triggers.
2. Classify them into risk categories with supplier-/lane-level risk scores.
3. Map each event to the affected parts of *our* network (suppliers, lanes,
   facilities) by retrieving from an internal supply-chain knowledge base.
4. Produce a demand forecast that visibly reflects disruption risk.
5. Run a discrete-event + Monte Carlo simulation yielding stockout probability and
   revenue-impact estimates.
6. Generate readable, business-relevant mitigation recommendations, grounded in
   historical disruptions and mitigation playbooks.
7. Present all of the above on an interactive dashboard with alerts.
8. Report evaluation metrics: classification accuracy, forecast deviation, and a
   qualitative simulation/recommendation quality check.

## Guiding principles

- **Always demoable** — keep a runnable end-to-end slice working at all times
  (see [[roadmap]]).
- **Right model for the job** — a large LLM (**Groq `gpt-oss-120b`**) reasons and
  orchestrates; lightweight fine-tuned classifiers handle high-volume execution work
  (see [[tech-stack]]).
- **Graceful degradation** — if a live source fails, fall back to cached/synthetic
  data rather than breaking the run.
- **Explainable over clever** — favor outputs an analyst can trust and justify.
