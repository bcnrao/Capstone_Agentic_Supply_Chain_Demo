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

## Scope: Capstone Demo / Proof of Concept

This is a **capstone POC**, not a production system. That choice drives every
trade-off below.

**Optimize for:**
- **Breadth** — a working end-to-end path through all nine agents that proves the
  multi-agent concept.
- **Demonstrability** — every run produces a clear, reproducible story a reviewer
  can follow on a dashboard.
- **Reproducibility** — demos must not break because an external API is down or
  rate-limited (see [[tech-stack]] data strategy).

**Explicitly out of scope for the POC (Phases 0–10):**
- Production hardening: HA, autoscaling, multi-tenant security, SLAs.
- Live trading/ERP integrations or write-back into real procurement systems.
- Real-money decisions — output is decision *support*, not automated action.

**Planned post-POC (Phases 11–12, see [[roadmap]]):**
- **Cloud deployment** — containerize and host the backend + dashboard with managed
  persistence and CI/CD.
- **Production frontend** — replace the Gradio dashboard with a dedicated React app
  backed by a service API.

These post-POC phases begin only once the capstone demo is complete and accepted;
they shift the project from "always-demoable POC" toward a production-leaning pilot.

## Primary users

- **Supply chain / risk analysts** — see ranked risks and simulated impact, explore
  "what-if" mitigations.
- **Operations & planning leads** — consume high-level alerts and recommended
  actions.
- **Capstone reviewers** — evaluate the system end-to-end against the metrics below.

## Success criteria

A successful POC can, in a single demo run:

1. Ingest disruption signals from a mix of live and cached/synthetic sources.
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
- **Right model for the job** — a large LLM reasons and orchestrates; lightweight
  fine-tuned classifiers handle high-volume execution work (see [[tech-stack]]).
- **Graceful degradation** — if a live source fails, fall back to cached/synthetic
  data rather than breaking the run.
- **Explainable over clever** — favor outputs an analyst can trust and justify.
