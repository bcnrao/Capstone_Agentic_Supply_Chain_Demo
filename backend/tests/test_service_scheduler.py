"""Scheduled poller — the job runs the pipeline once; job is overlap-safe. Offline."""

from agentic_scd.config.settings import Settings
from agentic_scd.ingestion import service
from agentic_scd.ingestion.service import POLL_JOB_ID, run_poll_cycle, start_scheduler


def offline_settings(**overrides) -> Settings:
    base = dict(
        groq_api_key=None,
        groq_model="unused",
        use_mock_llm=True,
        database_url=None,
        ingest_scheduler_enabled=True,
    )
    base.update(overrides)
    return Settings(**base)


def test_poll_cycle_invokes_collect_once(monkeypatch) -> None:
    calls: list[Settings] = []
    monkeypatch.setattr(
        service, "collect", lambda settings: calls.append(settings) or _Summary()
    )
    run_poll_cycle(offline_settings())
    assert len(calls) == 1


def test_poll_cycle_swallows_errors(monkeypatch) -> None:
    def boom(settings):
        raise RuntimeError("collect failed")

    monkeypatch.setattr(service, "collect", boom)
    # Must not raise out of the scheduler thread.
    run_poll_cycle(offline_settings())


def test_start_scheduler_registers_overlap_safe_job() -> None:
    scheduler = start_scheduler(offline_settings(ingest_poll_interval_minutes=5))
    try:
        job = scheduler.get_job(POLL_JOB_ID)
        assert job is not None
        assert job.max_instances == 1
        assert scheduler.running is True
        # The job must be actually scheduled (a paused job has next_run_time=None).
        assert job.next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)


class _Summary:
    """Minimal stand-in for CollectSummary used by the monkeypatched collect."""

    db_persisted = False

    @property
    def totals(self):
        from agentic_scd.ingestion.collect import SourceResult

        return SourceResult(name="TOTAL")
