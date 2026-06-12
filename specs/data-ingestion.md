# Data Ingestion Layer

The foundational data layer (Phase 1, see [[roadmap]]). It turns messy, source-specific
external data into clean, deduplicated, **relevant** disruption signals that the rest
of the pipeline consumes. Built first because everything downstream depends on it.

## Responsibility boundary

Ingestion runs as a **separate service** of independent **collectors** that
**fetch → normalize → relevance-gate → dedupe → persist** incoming signals to Postgres.
The pipeline then consumes them: `ingest_node` reads the new rows and the **input
guardrail** node validates them before the agents. Collectors and the pipeline are
**decoupled by the database** — neither blocks the other.

Ingestion does **not** categorize, score, or map impact — those are Phases 3/4.

One nuance worth stating clearly: ingestion performs **coarse relevance gating**
(a binary keep/drop: "is this a supply-chain disruption signal at all?"), but **not
classification** (which disruption category, how severe, which suppliers/lanes). The
gate is the bouncer checking you're at the right building; classification is the event
inside deciding your role. This keeps the DB free of irrelevant news while preserving
the clean separation of concerns.

## Connector (adapter) pattern

Every source — live or cached — implements one interface, so the pipeline treats them
uniformly and new sources are drop-in:

```python
class Connector(Protocol):
    name: str                 # "reuters_rss", "open_meteo", ...
    source_type: SourceType   # RSS | WEATHER | FREIGHT_INDEX | DATASET | SYNTHETIC
    reliability: float        # 0–1 prior, used downstream for confidence

    def fetch(self) -> list[RawItem]: ...      # live pull
    def fallback(self) -> list[RawItem]: ...   # cached/synthetic replay
```

A **source registry** (`sources.yaml`) lists enabled connectors, their URLs/query
terms, and fallback paths — so sources are toggled via config, not code.

### Sources (MVP)

- **RSS** (Supply Chain Dive, Reuters commodities/business, Google News *query-scoped*)
  via `feedparser`.
- **Open-Meteo** weather via `httpx` over a configured list of hubs/ports.
- **Freightos Baltic Index** as **cached snapshots** (no clean free API).
- **Kaggle SupplyChainNet** as a batch **dataset loader** (seeds history/baselines).
- **Supplier webhook** — partners POST events to a FastAPI endpoint in real time (push,
  not polled); the MVP drives it with a synthetic sender (HMAC signature auth is post-MVP).
- **Synthetic generator** for guaranteed demoable disruption scenarios.

## Canonical signal schema (`DisruptionSignal`)

One normalized record every connector maps into. Defined once (Pydantic + stored
version). Fields are filled across phases — ingestion fills only the neutral ones:

| Field | Filled by | Notes |
|-------|-----------|-------|
| `signal_id` | ingestion | UUID or content hash |
| `dedup_hash` | ingestion | hash of normalized title + body |
| `source`, `source_type`, `source_reliability` | ingestion | provenance |
| `fetched_at`, `event_time` | ingestion | event_time = published/forecast time (UTC) |
| `title`, `raw_text`, `url` | ingestion | normalized text |
| `raw_payload` | ingestion | original JSON, kept for audit/replay |
| `location` (region, lat/lon, hub/port) | ingestion *if available* | weather has it; news often not |
| `severity_hint` | ingestion *optional* | neutral hint only, not a score |
| `schema_version` | ingestion | migration safety |
| `category`, `severity` | **Phase 3** | null at ingestion |
| `affected_entities` | **Phase 4** | null at ingestion |

## Pipeline

```
collector:  fetch → normalize → relevance gate (Stage 0 + 1) → dedupe → persist (Postgres)
pipeline:   ingest_node reads new rows → input guardrail (schema · safety) → agents
```

### Normalize

Maps each source's raw format into the one canonical `DisruptionSignal` so everything
downstream sees identical fields. Also does light consistency fixes:
- **Dates** → UTC ISO timestamps (so heterogeneous source dates become comparable).
- **Text** → strip HTML, collapse whitespace, optional truncation.
- **Provenance** → stamp `source`, `source_type`, `source_reliability`.
- **Keep the original** → store untouched raw JSON in `raw_payload`.

Normalize runs **before** the gate and dedupe because both operate on clean text.

### Relevance gate (Stage 0 + Stage 1 only for the MVP)

Live news is mostly irrelevant to supply chains; storing all of it would bloat the DB.
A cheap funnel drops noise **before** persistence. The MVP ships the two free stages:

- **Stage 0 — Source targeting (free).** Subscribe only to supply-chain feeds and use
  *query-scoped* Google News feeds (`port strike`, `factory shutdown`, `shipping
  delay`, `tariff`, `port congestion`, …). Eliminates most noise at the source.
- **Stage 1 — Keyword/rule gate (free, deterministic).** Match normalized text against
  a curated **disruption lexicon** (strike, embargo, shortage, typhoon, blockade,
  congestion, recall, shutdown, tariff, …). Zero hits → drop.

> **Deferred — Stage 2 (DistilBERT binary relevance gate).** A lightweight
> "disruption-relevant? yes/no" classifier for ambiguous items. Not in the MVP's first
> cut; introduce alongside the DistilBERT work in Phase 3 if Stage 0+1 prove too noisy.

**Favor recall.** Dropping a real disruption (false negative) is worse than keeping
some noise, so tune the gate loosely, log the drop rate, and sample rejects during
development. Raw pulls are retained as snapshot files **outside** the DB (see Persist),
so an over-aggressive lexicon is recoverable by re-running with looser terms.

### Dedupe

The same event recurs (re-polled feeds, cross-outlet syndication, demo re-runs).
Without dedupe one event becomes many inflated "disruptions." Mechanism:

```python
dedup_hash = sha256(normalized_title + normalized_body).hexdigest()
# hash already seen? -> skip;  else -> persist + emit
```

Hashing the *normalized* text is why normalize must run first. MVP uses **exact**
hash dedupe (catches re-fetches + verbatim syndication). **Fuzzy** dedupe (same event,
different wording — embedding/title similarity) is deferred past the MVP.

### Persist

| Data | Where | Why |
|------|-------|-----|
| Accepted signals (full record + `raw_payload`) | **Local PostgreSQL** (system of record) | the working dataset; relational queries, easy dedupe/upsert |
| Rejected items' **`dedup_hash` only** | small "seen-rejected" table (TTL'd) | skip re-evaluating the same junk each poll, without storing its content |
| Raw feed pulls | **cached snapshot files** (also the fallback path), *not* the DB | audit/replay + re-tune the filter without data loss |

Postgres is also the **decoupled handoff** between the collector service and the
pipeline: collectors write accepted signals, and `ingest_node` reads only the **new**
rows (a `status` flag `new → processing → done`, or a watermark) — so a busy pipeline
never blocks ingestion and nothing is lost.

Optional Parquet export for analytics. A simple **retention/TTL** for accepted signals
is noted but not built in the first cut.

### Read into the graph (`ingest_node`)

Collection is decoupled from the graph: collectors persist to Postgres, and the graph's
`ingest_node` **reads** the new rows and returns a partial state update (not a message
bus — LangGraph merges it into a state channel the next node reads):

```python
def ingest_node(state: GraphState) -> dict:
    rows = read_new_signals()         # status 'new' -> mark 'processing'
    return {"new_signals": rows}      # merged via the channel reducer
```

- **State channel:** `new_signals: list[DisruptionSignal]`.
- **Reducer:** **overwrite-per-run** for the MVP (state holds this run's batch);
  local PostgreSQL is the durable accumulator. (Additive reducer available if needed later.)
- **Delta only:** `ingest_node` selects only rows not yet processed (status flag /
  watermark), so downstream never reprocesses old news.
- **Consumption:** downstream reads the batch and loops (simple). `Send` fan-out for
  per-signal parallelism is a later optimization.
- **Payload:** full objects in state at MVP volumes; switch to IDs-with-DB-load only
  if state gets heavy.

## Graceful degradation

Each connector's `fetch()` is wrapped so any failure (network, rate-limit, empty)
falls back to `fallback()` (cached/synthetic) instead of throwing. A run always yields
signals; the path taken (live vs fallback) is logged so the dashboard can show it.
This is the spec's "never break a demo" principle (see [[mission]]).

## Triggers & scheduling

Collectors run on **independent triggers** (the layer is a separate service), so the
system monitors continuously rather than only on demand:

- **Scheduled** — APScheduler/cron polls RSS + weather every N minutes (continuous
  monitoring, even with nobody at the dashboard).
- **Webhook** — supplier pushes arrive in real time at the FastAPI endpoint.
- **Batch** — the historical loader runs once at startup to seed baselines + the KB.
- **On-demand** — a manual run or dashboard "Refresh" still works for a guided demo.

The pipeline itself is re-invoked by a driver (scheduled / webhook / on-demand); each run's
`ingest_node` drains whatever has accumulated in Postgres. (Earlier the MVP was on-demand
only — scheduling and webhook ingestion are now in the MVP, not deferred.)

## LangGraph integration

The **collectors run as a separate service, outside LangGraph** — they only write to
Postgres. Inside the graph, **`ingest_node`** reads the new rows and the **input
guardrail** node validates them (relevance · Pydantic schema · safety → discard) before
the classification node. So the layer spans a non-LangGraph collector service plus two
pipeline nodes, joined by the database.

## Suggested structure

```
ingestion/                # separate collector service (outside LangGraph)
  connectors/   base.py, rss.py, open_meteo.py, freightos.py, kaggle.py, synthetic.py, webhook.py
  schema.py     # DisruptionSignal (Pydantic)
  normalize.py
  relevance.py  # Stage 0 config-driven targeting + Stage 1 keyword lexicon gate
  dedupe.py
  store.py      # PostgreSQL/Parquet + seen-rejected cache
  registry.py   # loads sources.yaml
  scheduler.py  # APScheduler/cron poller
  service.py    # FastAPI webhook endpoint + service entrypoint
pipeline/
  ingest_node.py    # reads new rows from Postgres -> graph state
  guardrails.py     # input guardrail (relevance · schema · safety -> discard)
sources.yaml
lexicon.yaml    # disruption keyword list for Stage 1
```

## Decisions

**Locked (MVP):** connector/adapter pattern; canonical `DisruptionSignal` schema;
relevance gate **Stage 0 + Stage 1 only**; exact-hash dedupe; **collectors as a separate
service** on multiple triggers (**scheduled poller + supplier webhook + batch + on-demand**);
local PostgreSQL system of record **and decoupled handoff** (collectors write, `ingest_node`
reads new rows via status flag/watermark) + rejected-hash cache + raw snapshot files;
**input guardrail** node (relevance · schema · safety → discard); overwrite reducer; batch
consumption; full objects in state.

**Deferred:** Stage 2 DistilBERT relevance gate (→ Phase 3); fuzzy dedupe; `Send`
fan-out; IDs-in-state; retention/TTL enforcement; HMAC webhook signature auth (→ post-MVP).
