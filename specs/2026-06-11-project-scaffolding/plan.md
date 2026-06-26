# Phase 0 — Project Scaffolding · Plan

Numbered task groups. Each group is independently reviewable; the order respects
dependencies (config + schema before the graph that uses them). Scope and decisions
in [[requirements]]; success criteria in [[validation]].

---

## 1. Repository & package skeleton
1.1 Create an importable Python package (e.g. `src/<pkg>/` with `__init__.py`).
1.2 Add top-level dirs that later phases will fill: `<pkg>/ingestion/`,
    `<pkg>/graph/`, `<pkg>/llm/`, `<pkg>/config/` (empty `__init__.py` placeholders).
1.3 Add a `tests/` directory.
1.4 Update `.gitignore` for Python (`__pycache__`, `*.pyc`, `.venv/`, `.env`,
    `*.sqlite`, build artifacts).

## 2. Dependency & build configuration (`uv`)
2.1 Initialize the project with **`uv`** (`uv init` / hand-authored `pyproject.toml`,
    PEP 621): project metadata, `requires-python = ">=3.11"`.
2.2 Add **only Phase-0 deps** — `uv add langgraph pydantic python-dotenv groq`;
    dev group — `uv add --dev pytest ruff`.
2.3 Configure `ruff` (lint + format) and `pytest` (testpaths) in `pyproject.toml`.
2.4 Commit the generated `uv.lock`; verify a clean sync: `uv sync` in a fresh checkout.

## 3. Configuration & `.env` handling
3.1 `config` module that loads env via `python-dotenv` (Groq API key, model name,
    a `USE_MOCK_LLM` / "no key → mock" switch).
3.2 Commit `.env.example` documenting every variable; ensure `.env` is git-ignored.

## 4. LLM wrapper stub
4.1 Thin `llm` module exposing a single `complete(prompt, ...)`-style entrypoint that
    centralizes provider calls (per [[tech-stack]]).
4.2 If no real API key is configured, return a deterministic **mock** response so the
    scaffold runs offline — upholds "always demoable" ([[mission]]).
4.3 Leave a clear seam for the real Groq call (used from Phase 3/7).

## 5. Shared schema stub (`DisruptionSignal`)
5.1 Pydantic model with **only the neutral, ingestion-filled fields** now
    (`signal_id`, `source`, `source_type`, `fetched_at`, `event_time`, `title`,
    `raw_text`, `url`, `schema_version`); Phase 3/4 fields declared
    `Optional`/nullable. Field rationale in [[data-ingestion]].
5.2 Include `schema_version` from the start for migration safety.

## 6. LangGraph state & stub node
6.1 Define typed `GraphState` with `new_signals: list[DisruptionSignal]` (the channel
    [[data-ingestion]] specifies), using the appropriate reducer.
6.2 Implement a single **stub node** that returns a partial state update (e.g. one
    synthetic placeholder signal) — proves the emit/merge mechanism.
6.3 Build/compile the LangGraph wiring the stub node.

## 7. Entrypoint
7.1 Implement a `main()` (e.g. `<pkg>/__main__.py` / `<pkg>/cli.py`) that builds the
    graph, invokes it, and prints/returns the resulting `GraphState`.
7.2 Declare it as a console script in `[project.scripts]` (e.g.
    `agentic-scd = "<pkg>.__main__:main"`) so it runs via `uv run <command>`;
    `python -m <pkg>` also works via `__main__.py`.
7.3 Confirm it runs end-to-end with **no real API key** present.

## 8. Quality baseline (CI-lite)
8.1 One `pytest` smoke test: importing the package, the entrypoint runs, the graph
    returns a `GraphState` containing `new_signals`.
8.2 Ensure `ruff check` and `ruff format --check` pass on the whole tree.
8.3 (Optional) A `make`/script shortcut or short README section documenting
    `uv sync → uv run → uv run pytest → uv run ruff`.

## 9. Docs & wrap-up
9.1 Brief package-level README (or update root `README.md`) with setup + run steps.
9.2 Confirm all [[validation]] criteria pass; open PR into `main`.
