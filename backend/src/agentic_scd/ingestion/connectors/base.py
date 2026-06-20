"""The connector (adapter) contract and the fallback wrapper.

Every source maps its raw records into ``RawItem`` and implements ``Connector``.
``fetch_with_fallback`` is the graceful-degradation seam: any ``fetch()`` failure
(network / rate-limit / empty) degrades to ``fallback()`` instead of raising, and the
path taken (live vs fallback) is logged — the spec's "never break a demo" principle.
"""

import logging
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SourceType:
    """Canonical source-type tags (mirrors ``DisruptionSignal.source_type``)."""

    RSS = "RSS"
    WEATHER = "WEATHER"
    FREIGHT_INDEX = "FREIGHT_INDEX"
    DATASET = "DATASET"
    SYNTHETIC = "SYNTHETIC"
    WEBHOOK = "WEBHOOK"


class RawItem(BaseModel):
    """A loosely-typed raw record as pulled from a source, pre-normalization.

    ``payload`` keeps the untouched original (audit/replay); the other fields are a
    best-effort common shape the normalizer reads. ``location`` carries structured
    geo when a source has it (weather does; news usually does not).
    """

    title: str = Field(default="", description="Raw title/headline, if any.")
    body: str = Field(default="", description="Raw body/summary text, if any.")
    url: str | None = Field(default=None, description="Source URL, if any.")
    published: str | None = Field(
        default=None, description="Raw published/forecast timestamp string, if any."
    )
    location: dict | None = Field(
        default=None, description="Structured geo (region/lat/lon/hub_port), if any."
    )
    payload: dict = Field(
        default_factory=dict, description="Untouched original record for audit/replay."
    )


@runtime_checkable
class Connector(Protocol):
    """One source adapter. ``fetch`` pulls live; ``fallback`` replays cached."""

    name: str
    source_type: str
    reliability: float

    def fetch(self) -> list[RawItem]: ...

    def fallback(self) -> list[RawItem]: ...


def fetch_with_fallback(connector: Connector) -> tuple[list[RawItem], str]:
    """Run ``connector.fetch()``; on any failure or empty result, use ``fallback()``.

    Returns ``(items, path)`` where ``path`` is ``"live"`` or ``"fallback"``. Never
    raises for a source failure — that is the whole point of the wrapper.
    """
    try:
        items = connector.fetch()
        if items:
            logger.info(
                "connector %s: live fetch -> %d item(s)", connector.name, len(items)
            )
            return items, "live"
        logger.warning("connector %s: live fetch empty -> fallback", connector.name)
    except Exception as exc:  # noqa: BLE001 — degrade on *any* source failure
        logger.warning(
            "connector %s: live fetch failed (%s) -> fallback", connector.name, exc
        )

    items = connector.fallback()
    logger.info("connector %s: fallback -> %d item(s)", connector.name, len(items))
    return items, "fallback"
