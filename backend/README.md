# agentic-scd — backend

The Python service for the **Agentic Supply Chain Disruption Predictor & Simulation
Engine**: the LangGraph pipeline, ingestion layer, agents, FastAPI/Gradio surfaces, and
the dev notebooks.

This directory is the Python project (`pyproject.toml` lives here). Run `uv` commands
from **here** (`cd backend`); run `docker compose` from the **repo root** (one level up),
where `docker-compose.yml` and `.env` live.

```bash
uv sync --group notebooks     # install deps (incl. Jupyter)
uv run agentic-scd            # run the end-to-end pipeline
uv run pytest                 # tests
```

## LangSmith Tracing (Optional)

Traces LangGraph pipeline runs to [LangSmith Cloud](https://smith.langchain.com).

1. Packages are already in `pyproject.toml` (`langgraph`, `langchain`, `langsmith`).

2. Set these in the **repo-root** `.env`:

   - `LANGSMITH_TRACING=true`
   - `LANGSMITH_API_KEY=<your_langsmith_api_key>`
   - `LANGSMITH_PROJECT=genAI` (optional)
   - Optional: `LANGSMITH_ENDPOINT`, `APP_NAME`, `APP_VERSION`, `APP_ENV`

3. Run the pipeline (`uv run agentic-scd` or `uv run agentic-scd-api`) and inspect the
   project in LangSmith. Runs are named **Supply Chain Disruption Pipeline**.

Docker Compose passes the same env vars into the `api` and `app` services. See the
repo-root README for full stack instructions.

See the **repo-root `README.md`** for the full quick start (Docker and uv paths),
architecture, and per-phase documentation.
