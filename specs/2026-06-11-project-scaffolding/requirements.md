# Phase 0 — Project Scaffolding · Requirements

> Roadmap phase: **Phase 0 — Project scaffolding** (see [[roadmap]]).
> Guidance: [[mission]] (capstone MVP; breadth, demonstrability, reproducibility),
> [[tech-stack]] (Python 3.11+, LangGraph, Groq `gpt-oss-120b`, local PostgreSQL, Chroma).

## Goal

Stand up the minimal runnable skeleton every later phase builds on: a Python package,
dependency/config management, a thin swappable LLM wrapper, the shared signal schema
and LangGraph state objects (as stubs), and a `python` entrypoint that runs an empty
LangGraph with one stub node.

**Roadmap "Done when":** `python` entrypoint runs an empty LangGraph with a stub node.

## In scope

1. **Repo structure** — an importable Python package for agent code (per
   [[tech-stack]]: "agent code lives in importable modules"). `specs/` already exists.
2. **Dependency management** — **`uv`** with `pyproject.toml` (PEP 621) as the source
   of truth and a committed `uv.lock` for reproducible installs. Only the dependencies
   Phase 0 actually imports are added now (langgraph, pydantic, python-dotenv, groq;
   dev: pytest, ruff). Heavier per-agent libs (Prophet, SimPy, transformers, Chroma,
   feedparser, httpx) are added (`uv add`) in the phase that needs them.
3. **Config / `.env` handling** — `python-dotenv` loads config; a `.env.example` is
   committed, `.env` is git-ignored. Secrets (Groq API key) never committed.
4. **LLM wrapper stub** — a thin module that centralizes provider calls so models can
   be swapped without touching agent logic (per [[tech-stack]]). For Phase 0 it loads
   config and returns a canned/mock response when no real API key is present, so the
   scaffold runs fully offline.
5. **Shared schema (stub)** — `DisruptionSignal` Pydantic model with **only the
   neutral, ingestion-filled fields** defined now; Phase 3/4 fields
   (`category`, `severity`, `affected_entities`) declared nullable/optional. Full
   field set lives in [[data-ingestion]] and is filled in Phase 1+.
6. **LangGraph state (stub)** — a typed `GraphState` with `new_signals:
   list[DisruptionSignal]` and a stub node that populates it, wired into a runnable
   graph.
7. **Entrypoint** — a console script declared in `[project.scripts]` so the graph
   runs via `uv run <command>` (e.g. `uv run agentic-scd`). It builds the graph,
   invokes it, and prints/returns the resulting state. (`python -m <pkg>` keeps
   working too via `__main__.py`.)
8. **Quality baseline (CI-lite)** — one `pytest` smoke test plus a `ruff`
   lint/format configuration, establishing the test/quality bar from day one.

## Out of scope (deferred to later phases)

- Real connectors, normalization, relevance gate, dedupe, persistence — **Phase 1**
  (full design already in [[data-ingestion]]).
- Full `DisruptionSignal` field set and the local PostgreSQL store — **Phase 1**.
- Any real agent logic (classify, impact-map, forecast, simulate, recommend) —
  **Phase 2+**.
- Real Groq calls / prompt engineering, Chroma/vector store, Gradio UI.
- Docker / `docker-compose` — **Phase 10** (a later MVP phase, not Phase 0).
- Hosted CI (GitHub Actions), cloud config — **post-MVP (Phase 12)**.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Schema depth | **Minimal stub**, expand in Phase 1 | Smallest blast radius; avoids guessing fields the ingestion spec will own. |
| Dependency mgmt | **`uv`** + `pyproject.toml` + `uv.lock` | Fast, reproducible, single source of truth; matches [[tech-stack]]. |
| LLM wrapper | Stub with **mock fallback** when no API key | Keeps the scaffold runnable offline → upholds the "always demoable" principle ([[mission]]). |
| Validation bar | Entrypoint + **smoke test + ruff** | Sets a quality baseline at the root so later phases inherit it. |
| Python | **3.11+** | Per [[tech-stack]]. |

## Open questions / notes

- Exact package name (e.g. `supply_chain` / `agentic_scd`) — pick the clearest at
  implementation time; record it in the package README.
- A `requirements.txt` may still be exported later if a consumer needs it
  (`uv export`), but `pyproject.toml` + `uv.lock` are the source of truth.
- Requires `uv` to be installed on the dev machine (standalone installer or `pipx`).
