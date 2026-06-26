# Demo Walkthrough & User Experience

How an end user actually uses the system, what they see on screen, and the exact
scenario we play out for the capstone demo. This is the *experience* companion to
[[mission]] (the "what & why") and [[roadmap]] (the build order).

---

## Who is driving, and what they want

The MVP ships two parallel surfaces over one **FastAPI** API ([[tech-stack]]): a
**Gradio** dashboard (fast / internal iteration) and a **React** app (product-facing).
They present the same views; this walkthrough describes what a user sees on either.

- **Supply chain / risk analyst** — the primary driver. Opens the dashboard, sees
  what is at risk *right now*, drills into a specific disruption, and tweaks
  mitigation assumptions to compare options.
- **Operations / planning lead** — a lighter consumer. Glances at the top alerts and
  the recommended actions; rarely runs a simulation by hand.
- **Capstone reviewer** — follows the scripted demo below to see all seven agents fire
  end-to-end, then reads the evaluation panel to judge quality.

The core promise to all three: **turn noisy external signals into a ranked,
quantified, explainable picture of risk to *our* network — and a recommended action.**

---

## What the user sees: dashboard layout

Either UI — the Gradio dashboard, mirrored by the React app — presents a top-level run
control and a set of tabs/panels that map one-to-one onto the agent pipeline, so the
reviewer can literally watch state flow from agent to agent.

**Top bar (always visible)**
- **"Run pipeline"** button + a scenario/seed selector (live · cached · synthetic). The
  system also ingests **continuously** (scheduled poller + supplier webhook), so the alert
  list refreshes on its own between manual runs.
- A run-status strip showing each stage lighting up as it completes
  (ingest → input-guard → classify → impact-map → forecast → simulate → mitigate →
  output-guard), so progress is visible and the multi-agent chain is legible.

**Panel 1 — Risk overview (landing)**
- A **ranked alert list** of active disruptions (highest risk first) with category,
  risk score, and the suppliers/lanes affected.
- A **disruption heatmap / map** highlighting affected regions, lanes, and facilities
  in *our* network.
- This is the "what's on fire" view the ops lead can read in five seconds.

**Panel 2 — Signal & classification detail** (click any alert)
- The originating signal(s): headline, source, timestamp, extracted entities.
- The agent's read: **disruption category** + numeric **supplier-/lane-level risk
  score**, with the extracted rationale (the news/event analysis output).

**Panel 3 — Impact mapping**
- The concrete parts of *our* network this event touches: named suppliers,
  facilities, trade lanes, commodities — retrieved from the internal supply-chain
  knowledge base (RAG), not guessed.

**Panel 4 — Demand forecast**
- A baseline demand curve vs. the **risk-adjusted** curve, so the user sees the
  forecast visibly bend in response to the active disruption.

**Panel 5 — Simulation outcomes**
- Results of the discrete-event + Monte Carlo run: **stockout probability** and a
  **revenue-impact distribution** (with confidence band), plus the key assumptions.
- This is where the **what-if** controls live (see below).

**Panel 6 — Mitigation recommendations**
- Readable, business-relevant recommended actions (alternate suppliers, reroute,
  safety-stock change), each **grounded in precedent** (cited historical disruption /
  playbook) and tied to the simulated impact it is meant to reduce.

**Panel 7 — Evaluation**
- A metrics summary: classification accuracy, forecast deviation, and a qualitative
  simulation/recommendation quality check — so a reviewer can judge system quality,
  not just watch it run.

---

## The capstone demo scenario: Taiwan earthquake → semiconductors

A single, seeded, reproducible scenario chosen because it exercises **every** agent
with a recognizable, high-stakes story: a major earthquake near Taiwan's
semiconductor cluster cascades into our electronics supply chain.

The demo is delivered as a **guided single run, then an interactive what-if** — the
analyst runs the full chain once, then explores a mitigation live.

### Act 1 — One guided end-to-end run

The presenter selects the seeded "Taiwan earthquake" scenario and clicks
**Run pipeline**. The reviewer watches the run-status strip advance and each panel
populate in order:

1. **Ingestion** — collectors (scheduled poller / webhook / the seeded injector) have
   written a mix of live RSS + a cached/synthetic earthquake signal to Postgres,
   normalized and deduped; `ingest_node` reads the new rows and the **input guardrail**
   drops anything unsafe / off-topic. (If a live source is down, graceful fallback to
   cached/synthetic keeps the demo intact.)
2. **News & event analysis** — the LLM (Groq `gpt-oss-120b`) classifies the earthquake
   item as a *natural-disaster / supplier-outage* disruption and extracts entities
   (region, affected industry, severity).
3. **Risk classification** — DistilBERT attaches a disruption category and a numeric
   supplier-/lane-level **risk score**; the item jumps to the top of the alert list.
4. **Impact mapping (RAG)** — retrieval over the internal KB links the event to
   *our* specific Taiwan-based chip suppliers, the trans-Pacific lanes they feed, and
   the downstream assembly facilities — shown in Panel 3.
5. **Demand forecasting (Prophet)** — Panel 4 shows the electronics demand forecast
   re-shaped by the disruption risk vs. the undisturbed baseline.
6. **Simulation (SimPy + Monte Carlo)** — Panel 5 quantifies the hit: stockout
   probability for affected SKUs and a revenue-impact distribution.
7. **Mitigation recommendations (RAG-grounded)** — Panel 6 produces ranked actions
   (e.g. shift volume to an alternate supplier, expedite freight, raise safety stock),
   each citing a relevant past disruption and pointing at the impact it reduces. The
   **output guardrail** validates the plan (schema · urgency · action count; retry once,
   else a default) before it reaches the dashboard.
8. **Dashboard & alerting** *(presentation layer, not an agent)* — all of the above is
   already rendered; the high-risk alert is flagged at the top of Panel 1.
9. **Evaluation** *(metrics step, not an agent)* — Panel 7 reports the run's metrics;
   the full run is also traced in **Langfuse** (local) for debugging.

At the end of Act 1 the reviewer has seen all seven agents fire — then the dashboard
render and the evaluation panel report — producing one coherent, explainable story from
raw signal to recommended action.

### Act 2 — Interactive what-if

The analyst now stays on **Panel 5** and explores a mitigation without re-running
ingestion/classification:

- Adjust a what-if control — e.g. **switch 40% of volume to the alternate supplier**
  surfaced in Panel 6, or **add two weeks of safety stock**.
- Re-run the simulation; the stockout probability and revenue-impact distribution
  update, and Panel 6's recommendation framing updates to reflect the chosen
  mitigation.
- The takeaway the demo lands: the system is **decision support** — it lets a human
  compare mitigation options on quantified outcomes, not just read a static report.

---

## What "good" looks like in the demo

Tied directly to the [[mission]] success criteria — the demo is "done" when, in one
seeded run, the dashboard shows: a ranked disruption, the concrete network entities
it hits, a bent demand forecast, quantified stockout/revenue impact, precedent-cited
recommendations, and a metrics panel — and the what-if visibly changes the simulated
outcome. Per [[mission]]'s *graceful degradation* principle, none of this breaks if a
live source is unavailable, because the scenario is seeded and every source has a
cached/synthetic fallback.
