"""Supplier webhook: request model + source identity.

A supplier (or, in the MVP, the synthetic sender) POSTs a disruption event as JSON.
``WebhookEvent`` validates that payload and ``to_raw_item`` maps it to the canonical
``RawItem`` so it flows through the *same* normalize -> gate -> dedupe -> persist path
as every other source — the webhook adds a trigger, not a second pipeline.
``WebhookSource`` is the provenance stamp ``normalize`` reads (name / source_type /
reliability); it is not a polling ``Connector`` (events are pushed, not fetched).
"""

from pydantic import BaseModel, Field

from agentic_scd.config import Settings, get_settings
from agentic_scd.ingestion.connectors.base import RawItem, SourceType

WEBHOOK_SOURCE_NAME = "supplier_webhook"


class WebhookEvent(BaseModel):
    """A supplier-pushed disruption event (the webhook request body)."""

    title: str = Field(..., description="Event headline (required).")
    body: str = Field(default="", description="Event detail/body text.")
    url: str | None = Field(default=None, description="Source URL, if any.")
    published: str | None = Field(
        default=None, description="Event timestamp (RFC-822 or ISO-8601), if any."
    )
    location: dict | None = Field(
        default=None, description="Structured geo (region/lat/lon/hub_port), if any."
    )
    payload: dict = Field(
        default_factory=dict,
        description="Extra supplier fields, kept for audit/replay.",
    )

    def to_raw_item(self) -> RawItem:
        """Map this event to a canonical ``RawItem`` (the pre-normalize shape)."""
        return RawItem(
            title=self.title,
            body=self.body,
            url=self.url,
            published=self.published,
            location=self.location,
            payload={"webhook_event": self.model_dump(), **self.payload},
        )


class WebhookSource:
    """Provenance identity for pushed events (duck-typed for ``normalize``)."""

    source_type = SourceType.WEBHOOK

    def __init__(self, reliability: float, name: str = WEBHOOK_SOURCE_NAME) -> None:
        self.name = name
        self.reliability = reliability


def webhook_source(settings: Settings | None = None) -> WebhookSource:
    """Build the webhook source with the configured reliability prior."""
    settings = settings or get_settings()
    return WebhookSource(reliability=settings.webhook_source_reliability)
