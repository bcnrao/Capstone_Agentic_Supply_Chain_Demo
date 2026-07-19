# Agentic Supply Chain Disruption Predictor & Simulation Engine
## End-to-End Flow, Engine Internals, and Design Rationale

---

## 1. One-line pitch

A LangGraph-orchestrated multi-agent pipeline that turns a raw disruption signal (news item, weather alert, webhook event) into a quantified business answer — *stockout probability, revenue at risk, recovery time* — and a guardrail-validated mitigation plan, in a single run.

---

## 2. How an event flows through the system

**Step 1 — Ingestion.** Signals enter through decoupled collectors: RSS feeds, the Open-Meteo weather API, the Freightos/Kaggle batch loaders, a synthetic generator, and a FastAPI webhook for real-time pushes. Collectors never call the pipeline directly — they write rows to a Postgres `signals` table with `status='new'`. The pipeline's ingestion node drains only those pending rows. This decoupling means a slow pipeline never blocks ingestion, and ingestion failures never break a demo run (every connector degrades to a cached fallback).

**Step 2 — Input guardrail.** Before any agent sees a signal, it must pass relevance targeting, a keyword lexicon gate, Pydantic schema validation, and a safety check. Off-topic or malformed events are discarded here — garbage never propagates downstream.

**Step 3 — News & Weather enrichment.** Two parallel enrichment agents run: the News agent extracts event type, entities and a severity hint via the LLM; the Weather agent pulls a 7-day forecast for monitored hubs (Shanghai, Rotterdam, LA) and scores port disruption risk.

**Step 4 — Classification (the routing decision).** A three-tier ensemble (keyword lexicon → DistilBERT zero-shot → Groq LLM fallback) assigns a category, then a severity score 1–10 is computed from keyword evidence, source reliability, the severity hint, and weather risk. Severity drives **conditional routing**:

| Severity | Route | What runs |
|---|---|---|
| > 7 (HIGH) | `high_path_simulation_first` | Skip impact + forecast → straight to Simulation → Recommend. Time-critical events get an answer fastest. |
| 4–7 (MEDIUM) | `full_path` | Impact → Forecast → Simulation → Recommend (everything). |
| < 4 (LOW) | `monitor_only` | Recommend (monitoring advice) only. No compute wasted on noise. |

Edge case we handle explicitly: if a HIGH signal arrives in the same batch as MEDIUM signals, the run falls back to `full_path` so the MEDIUM signals still get impact mapping and forecasting — the HIGH signal's risk is folded into the simulation regardless.

**Step 5 — Impact mapping (RAG #1).** The classified event is grounded to *our* network: a retriever searches the supply-chain knowledge base (suppliers, trade lanes, facilities, products from `network.json` + the Kaggle seed) and attaches the concrete entities at risk — e.g. a Shanghai typhoon maps to Supplier A, the Shanghai–LA lane, and the LA Import DC.

**Step 6 — Demand forecast.** Prophet fits the historical weekly demand series and projects an 8-week baseline; the baseline is then bent downward by a disruption factor derived from aggregate risk, impact count, freight-rate pressure (FBX index), and the disruption *category* (a strike suppresses demand differently than a port delay).

**Step 7 — Simulation.** The forecast's demand-suppression ratio, the impact map's lane transit times and supplier reliability, and the classification's risk score all feed a Monte Carlo loop (default 300 iterations) around a SimPy discrete-event model of a 4-node chain: **Supplier → Port → Warehouse → Retailer**. Output: stockout probability, expected shortage, revenue loss (P50/P90), recovery days, service level.

**Step 8 — Recommendation (RAG #2) + Output guardrail.** The mitigation retriever pulls matching playbooks from the historical-disruption corpus; the LLM composes concrete actions (alternate supplier, reroute, safety-stock change) grounded in that precedent plus the simulation numbers. An **output guardrail** validates the plan (schema, urgency vocabulary, action count), normalizes it, and substitutes a safe default plan if validation fails — the dashboard never renders a malformed result.

**Step 9 — Dashboard.** Gradio renders the whole run: classifications, weather risk, impact map, baseline-vs-adjusted forecast, simulation KPIs, recommendations, and the raw trace JSON.

---

## 3. Engine I/O summary table

| # | Engine | Input | Processing | Output |
|---|---|---|---|---|
| 1 | Ingestion | RSS / Open-Meteo / webhook / batch / synthetic sources | Fetch → normalize → relevance gate → dedupe (hash) → persist (`status='new'`) | Normalized `DisruptionSignal` rows in Postgres |
| 2 | Input guardrail | Pending signals | Relevance + schema + safety validation | Clean `new_signals` in graph state |
| 3 | News analysis | Signal text | LLM event extraction & summarization | `EventAnalysis` (event type, entities, severity hint) |
| 4 | Weather risk | Hub coordinates | 7-day Open-Meteo forecast → per-hub risk scoring | `WeatherRiskAssessment` (peak day, port disruption risk, affected ops) |
| 5 | Classify | Signal + analysis + weather | Keyword lexicon → DistilBERT zero-shot (≥0.5 conf) → Groq fallback; severity formula; route selection | `Classification` (category, severity 1–10, risk score, route) |
| 6 | Impact map | Classification + signal region | RAG retrieval over network KB with category hints | `ImpactMap` (affected suppliers, lanes, facilities, products) |
| 7 | Forecast | Classifications + impacts + demand history | Prophet baseline → risk/category/freight-adjusted projection | `Forecast` (baseline vs adjusted 8-week series, deviation %, inventory days, delay days) |
| 8 | Simulate | Classifications + impacts + forecast | 300× Monte Carlo over SimPy 4-node discrete-event model, 90-day window | `Simulation` (stockout prob, shortage units, revenue loss P50/P90, recovery days, service level) |
| 9 | Recommend | All upstream state | RAG over mitigation playbooks + LLM action generation | `Recommendation` (prioritized actions with urgency, owner, expected impact) |
| 10 | Output guardrail | Recommendation | Schema/urgency/action-count validation, normalization, safe fallback | Validated plan for the dashboard |

---

## 4. Processing detail per engine

### Classification — how severity and the route are computed

Category comes from a three-tier ensemble. Tier 1 counts keyword hits per category from a curated lexicon (interpretable, instant, free). Tier 2 runs DistilBERT zero-shot classification over the same label set and **overrides the keyword pick when its confidence ≥ 0.5**. Tier 3: below that threshold, a Groq LLM zero-shot call breaks the tie. A history retriever over past signals adds a corroboration bonus.

Severity is a transparent additive score:

```
base = 2.0 + 1.05 × keyword_hits + 2.0 × source_reliability + hint_bonus(none 0 … severe 3.5)
     + 1.0 if a WEATHER-source signal classified as weather
     + 0.8 if weather/labor category with ≥ 2 keyword hits
     + (0.5 + 1.5 × port_disruption_risk) if a hub weather assessment exists
severity = clamp(base, 1, 10);   risk_score = severity / 10
```

Because every term is inspectable, the dashboard's rationale column can explain *why* an event scored 7.15 — a deliberate contrast to a black-box score.

### Forecast — baseline, then bend it by risk

**Baseline:** Prophet fits the weekly demand series (from the DB if seeded, else the packaged Kaggle-derived CSV; requires ≥ 12 points) with seasonality disabled at this data scale, and projects 8 weeks of `yhat`. If Prophet is unavailable or data-starved, a numpy local-trend fit takes over — the run never fails, and the dashboard note tells you which engine produced the baseline.

**Adjustment:** a single disruption factor scales down the baseline, ramping over the horizon (disruptions bite harder in later weeks):

```
disruption_factor = min(0.62, risk × (0.16 + 0.022 × impact_count) × category_multiplier
                              + max(0, freight_delta) × 0.55)
adjusted[w] = baseline[w] × (1 − disruption_factor × (w+1)/8 + recovery_term)
```

- `freight_delta` = mean of the last 4 Freightos Baltic Index weekly changes — rising freight rates amplify the demand shock; falling rates add a small late-horizon recovery.
- `category_multiplier` encodes that disruption types differ at equal risk: labor strike 1.20 (production stops at once), demand shock 1.15, weather 1.10 (acute but recovers), logistics 0.85 (delays supply more than demand).
- Derived KPIs: demand deviation % (adjusted vs baseline totals), inventory days left = `26 × (1 − risk) + 4`, predicted delay days = `risk × 12 + 0.7 × impacts + 18 × freight_delta`.

### Simulation — SimPy discrete-event core inside a Monte Carlo shell

Each of the 300 iterations simulates a **90-day quarter** of a 4-node chain with parameters drawn from distributions calibrated on the Kaggle dataset EDA:

- **Supplier**: capacity `max(2, ⌊8 × (1 − 0.6 × risk)⌋)` concurrent orders — at high risk the supplier runs a skeleton crew and orders queue. Each order's lead time ~ Normal(16 d, 8.8 d) (dataset EDA values).
- **Port**: capacity shrinks with risk; clearance delay ~ Exponential(0.5 + 1.5 × risk + 0.1 × affected_nodes) days.
- **Transit**: lane-specific days from the impact map (e.g. Shanghai–LA = 17 d), inflated `× (1 + 0.15 × risk)`, with 10% noise.
- **Defects**: a risk-scaled fraction of each shipment is lost on receipt.
- **Retailer**: drains inventory daily at 30 units/day × the forecast's disruption ratio (mean adjusted ÷ mean baseline, clamped 0.5–1.0) — this is the explicit **Forecast → Simulation coupling**: Prophet's demand suppression directly changes simulated demand.
- **Realism fix worth mentioning**: opening inventory includes a "pre-transit credit" for stock already on the water when the disruption hits, scaled by `(1 − risk)²` — at risk 0 you get full credit, at risk 0.9 almost none. 8 replenishment shipments are staggered every 8 days.

Per iteration the engine records whether a stockout occurred, shortage units, revenue lost (₹18/unit), recovery time, and service level. Across 300 iterations, Monte Carlo aggregation yields **stockout probability** (fraction of iterations with a stockout) and the **P50/P90 revenue-loss distribution** — a range with confidence, not a single guess. On the HIGH route (forecast skipped), the demand ratio defaults to a pure risk-scaled value, so simulation still runs sensibly.

### Recommendation + output guardrail

The mitigation retriever searches the playbook corpus by category; retrieved precedent plus the classification, impact map, and simulation KPIs are packed into a JSON payload for the LLM (temperature 0) which returns structured actions. Urgency is derived from severity **and** simulated stockout probability. The guardrail then enforces the contract: valid urgency vocabulary, non-empty action text, owner assigned, action count bounds — retry once, else a safe monitoring plan. The UI can never receive a hallucinated or malformed plan.

---

## 5. Why these methods

**DistilBERT for classification.** DistilBERT retains ~97% of BERT's language understanding at 40% fewer parameters and ~60% faster inference, so it runs on CPU inside the demo environment with no GPU and no API cost. Used in zero-shot mode, it needs no labeled training set — critical because we have no annotated disruption corpus. It is deterministic and local, which the demo depends on. The ensemble design is the real point: keywords give interpretability, DistilBERT gives semantic generalization beyond the lexicon, and the Groq LLM is invoked only when confidence < 0.5 — accuracy where needed, near-zero cost and latency in the common case.

**Prophet for forecasting.** Prophet is an additive decomposable model (trend + seasonality + holidays) built for exactly this shape of business time series: short, weekly, gappy, outlier-prone. It fits robustly on a few dozen points where ARIMA needs careful order tuning and deep models (LSTM/transformers) would badly overfit. Its components are interpretable — we can show the reviewer the trend Prophet found — and it's the de-facto industry baseline for demand forecasting, so the choice is defensible. Our design keeps Prophet responsible for the *baseline* only; the risk adjustment is an explicit, explainable formula layered on top, so the disruption effect is never buried inside model weights.

**SimPy for simulation.** Stockouts are caused by *queues and contention* — orders waiting for supplier capacity, ships waiting for port slots — which closed-form spreadsheet math cannot represent. Discrete-event simulation models exactly that: SimPy's process-based generators map one-to-one onto real entities (a shipment is literally a process that requests a supplier slot, then a port slot, then transits). SimPy is pure Python, lightweight, and battle-tested, so it embeds cleanly in a LangGraph node with no external simulator. Wrapping it in Monte Carlo converts one uncertain story into a **distribution** — stockout *probability* and P90 revenue loss are what an operations leader can act on, and no analytic formula produces them for a queueing network.

**LangGraph for orchestration.** The pipeline is not a fixed chain — HIGH/MEDIUM/LOW conditional routing requires a graph with conditional edges and a shared typed state that every agent reads and writes. LangGraph gives exactly that, plus node-level observability. A `SimpleGraph` fallback executes the same node functions sequentially if LangGraph is absent — the architecture degrades, the demo doesn't.

**RAG (impact + mitigation) instead of pure LLM.** The LLM doesn't know *our* suppliers, lanes, or playbooks. Retrieval grounds impact mapping in the actual network KB and grounds recommendations in real precedent — cited, checkable evidence instead of plausible invention.

**Groq (gpt-oss-120b) as the LLM tier.** Very low latency for a live demo, and the wrapper returns a deterministic mock when no API key is set — the entire pipeline runs fully offline, which is our graceful-degradation guarantee.

---

## 6. Numbers to have ready in the demo

- 8-week forecast horizon; Prophet needs ≥ 12 weekly points, else local-trend fallback.
- Severity thresholds: > 7 HIGH, 4–7 MEDIUM, < 4 LOW. DistilBERT acceptance threshold: 0.5.
- Simulation: 300 Monte Carlo iterations (env-configurable), 90-day window, 8 shipments, lead time N(16, 8.8) d, default lane transit 17 d (Shanghai–LA), demand 30 u/day, revenue ₹18/unit short.
- Disruption factor cap: 0.62 (demand never modeled to collapse more than ~62%).
- Example run (typhoon → Shanghai): weather / severity 7.15 → HIGH route → stockout probability ≈ 0.88, guardrail-validated 2-action plan.
