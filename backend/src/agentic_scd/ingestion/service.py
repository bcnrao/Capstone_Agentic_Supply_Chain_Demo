"""The always-on ingestion service (console script ``agentic-scd-ingest``).

A single FastAPI process that hosts the **supplier webhook** and runs an in-process
**APScheduler poller** — the two always-on triggers added in Phase 1b on top of the
Phase 1a on-demand pipeline. Both write through the same normalize -> gate -> dedupe ->
persist path into the same Postgres handoff that ``ingest_node`` drains; neither blocks
the pipeline. Graceful: with no DB the service still starts, the poller ticks in-memory,
and the webhook returns cleanly with nothing persisted (never a 5xx for that case).
"""

import logging
from contextlib import asynccontextmanager

import psycopg
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request

from agentic_scd.config import Settings, get_settings
from agentic_scd.db import DatabaseNotConfiguredError, connect, init_db, ping
from agentic_scd.ingestion.collect import collect
from agentic_scd.ingestion.normalize import normalize
from agentic_scd.ingestion.pipeline import ingest_signals
from agentic_scd.ingestion.webhook import WebhookEvent, webhook_source

logger = logging.getLogger(__name__)

POLL_JOB_ID = "ingestion_poll"


def open_connection(settings: Settings):  # noqa: ANN201 — psycopg conn | None
    """Open a DB connection, or return ``None`` when none is reachable (graceful)."""
    try:
        return connect(settings)
    except (DatabaseNotConfiguredError, psycopg.OperationalError) as exc:
        logger.warning("ingestion service: no DB available (%s)", exc)
        return None


def run_poll_cycle(settings: Settings) -> None:
    """One scheduled poll: run every enabled connector through the pipeline once.

    Wraps ``collect`` so a failing cycle never escapes the scheduler thread.
    """
    try:
        summary = collect(settings)
        totals = summary.totals
        logger.info(
            "poll cycle done (persist=%s): fetched=%d kept=%d dropped=%d persisted=%d",
            summary.db_persisted,
            totals.fetched,
            totals.kept,
            totals.dropped,
            totals.persisted,
        )
    except Exception:  # noqa: BLE001 — a poll cycle must never kill the scheduler
        logger.exception("poll cycle failed")


def start_scheduler(settings: Settings) -> BackgroundScheduler:
    """Start an in-process poller running ``run_poll_cycle`` every N minutes."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_poll_cycle,
        trigger="interval",
        minutes=settings.ingest_poll_interval_minutes,
        args=[settings],
        id=POLL_JOB_ID,
        max_instances=1,  # a slow cycle never stacks on the next tick
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "scheduler started: polling every %d min", settings.ingest_poll_interval_minutes
    )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure the schema exists and run the scheduler for the app's lifetime."""
    settings: Settings = app.state.settings
    init_db(settings)  # idempotent; no-op when already created or no DB
    app.state.scheduler = None
    if settings.ingest_scheduler_enabled:
        app.state.scheduler = start_scheduler(settings)
    else:
        logger.info("scheduler disabled (INGEST_SCHEDULER_ENABLED=false)")
    try:
        yield
    finally:
        if app.state.scheduler is not None:
            app.state.scheduler.shutdown(wait=False)
            logger.info("scheduler stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI ingestion service app."""
    settings = settings or get_settings()
    app = FastAPI(title="Agentic SCD — ingestion service", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    def health(request: Request) -> dict:
        scheduler = getattr(request.app.state, "scheduler", None)
        return {
            "status": "ok",
            "scheduler_running": bool(scheduler and scheduler.running),
            "db_reachable": ping(request.app.state.settings).ok,
        }

    @app.post("/signals")
    def post_signal(event: WebhookEvent, request: Request) -> dict:
        """Ingest one supplier-pushed event through the shared pipeline tail."""
        cfg: Settings = request.app.state.settings
        signal = normalize(event.to_raw_item(), webhook_source(cfg))
        conn = open_connection(cfg)
        try:
            result = ingest_signals([signal], conn)
        finally:
            if conn is not None:
                conn.close()
        return {
            "kept": result.kept,
            "dropped": result.dropped,
            "persisted": result.persisted,
            "duplicate": result.duplicate,
            "persisted_to_db": conn is not None,
        }

    @app.post("/collect")
    def post_collect(request: Request) -> dict:
        """Trigger an on-demand collection across all enabled connectors."""
        summary = collect(request.app.state.settings)
        return {
            "db_persisted": summary.db_persisted,
            "sources": [
                {
                    "name": r.name,
                    "fetched": r.fetched,
                    "kept": r.kept,
                    "dropped": r.dropped,
                    "persisted": r.persisted,
                    "fallback_used": r.fallback_used,
                }
                for r in summary.results
            ],
        }

    return app


def main() -> None:
    """CLI entrypoint: serve the ingestion app with uvicorn."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    uvicorn.run(
        create_app(settings), host=settings.ingest_host, port=settings.ingest_port
    )


if __name__ == "__main__":
    main()
