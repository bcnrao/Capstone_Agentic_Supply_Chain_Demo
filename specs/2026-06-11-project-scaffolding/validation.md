# Phase 0 — Project Scaffolding · Validation

How we know Phase 0 is complete and the branch can merge to `main`. Maps to the
roadmap "Done when" and the [[requirements]] scope. Plan in [[plan]].

## Primary acceptance criterion (roadmap)

> **Done when:** `python` entrypoint runs an empty LangGraph with a stub node.

✅ Running the entrypoint (`uv run <command>`, e.g. `uv run agentic-scd`; `python -m
<pkg>` also works) builds a LangGraph, invokes it, and prints/returns a `GraphState`
— **with no real API key configured** (offline-runnable per [[mission]]'s "always
demoable" principle).

## Acceptance checklist

### Environment & build
- [ ] `uv sync` succeeds on a clean checkout from `pyproject.toml` + `uv.lock`.
- [ ] `uv.lock` is committed and reproduces the same resolution.
- [ ] `requires-python = ">=3.11"` enforced; `uv` selects/refuses Python accordingly.
- [ ] Only Phase-0 dependencies are declared (no Prophet/SimPy/transformers/Chroma yet).

### Config & secrets
- [ ] `.env.example` is committed and lists every variable used.
- [ ] `.env` is git-ignored; **no secret is committed** (`git log -p` / scan clean).
- [ ] Config loads via `python-dotenv`; missing optional vars degrade gracefully.

### LLM wrapper
- [ ] `llm` module exposes a single provider-agnostic call (swap-without-touching-agents).
- [ ] With **no API key**, it returns a deterministic mock response (no network call,
      no exception).

### Schema & state
- [ ] `DisruptionSignal` (Pydantic) defines only the neutral ingestion fields now;
      Phase 3/4 fields are `Optional`/nullable; `schema_version` present.
- [ ] `GraphState` is typed and carries `new_signals: list[DisruptionSignal]`.

### Graph & entrypoint
- [ ] A single stub node returns a partial state update that merges into `new_signals`.
- [ ] A console script is declared in `[project.scripts]`; `uv run <command>` runs
      the compiled graph and emits a populated `GraphState`.

### Quality baseline (CI-lite)
- [ ] `pytest` smoke test passes: package imports, entrypoint runs, returned state
      contains `new_signals`.
- [ ] `ruff check` passes (no lint errors).
- [ ] `ruff format --check` passes (formatting consistent).

## Commands (expected to pass)

```bash
uv sync                       # create .venv + install from pyproject.toml + uv.lock

uv run agentic-scd            # console script: prints/returns a GraphState with new_signals — runs offline
uv run pytest -q              # smoke test green
uv run ruff check .           # clean
uv run ruff format --check .  # clean
```

## Definition of done (merge gate)

All checklist boxes ticked, the four commands above pass on a clean checkout with **no
`.env`/API key**, and the work is scoped to Phase 0 only (no Phase 1+ logic leaked in).
Open a PR from `phase-0-scaffolding` into `main`; merge once the above is verified.

## Explicitly NOT validated here (later phases)
- Real connectors, normalization, relevance gate, dedupe, local PostgreSQL persistence — Phase 1.
- Real Groq responses, classification, impact mapping, forecasting, simulation,
  recommendations, dashboard — Phase 2+.
