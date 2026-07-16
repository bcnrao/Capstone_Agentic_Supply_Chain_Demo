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

To enable LangSmith tracing for monitoring and debugging the LangGraph pipeline:

1. Install the required packages (already included in `pyproject.toml`):
   - `langchain`
   - `langsmith`

2. Set the following environment variables (you can add them to your `.env` file in the repo root):
   - `LANGCHAIN_TRACING_V2=true`
   - `LANGCHAIN_API_KEY=<your_langchain_api_key>`
   - `LANGCHAIN_PROJECT=<optional_project_name>` (defaults to "default")

Once configured, each run of the pipeline will be automatically traced and sent to LangSmith.

See the **repo-root `README.md`** for the full quick start (Docker and uv paths),
architecture, and per-phase documentation.
