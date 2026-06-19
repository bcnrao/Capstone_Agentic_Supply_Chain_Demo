"""Synthetic disruption-scenario connector.

A deterministic generator of guaranteed-demoable disruption scenarios. Promotes the
Phase 0 ``synthetic_signal`` stub into a real connector and serves as the ultimate
fallback — it is always available, needs no network, and never fails, so a fully
offline run always yields signals. ``fetch`` and ``fallback`` are identical.
"""

from agentic_scd.ingestion.connectors.base import RawItem, SourceType

# Fixed, on-topic scenarios (the dedupe stage de-dupes re-runs; relevance keeps them).
SCENARIOS: list[dict[str, str]] = [
    {
        "title": "Port strike halts container shipments at major hub",
        "body": (
            "A labor strike has stopped container handling, causing shipping delays "
            "and port congestion expected to ripple across supply chains."
        ),
    },
    {
        "title": "Typhoon forces factory shutdown across manufacturing region",
        "body": (
            "A typhoon warning has triggered a factory shutdown and a temporary "
            "blockade of inland freight routes, threatening component shortages."
        ),
    },
    {
        "title": "New tariff disrupts cross-border supplier logistics",
        "body": (
            "A newly announced tariff has disrupted supplier logistics, with embargo "
            "concerns and a product recall compounding the shortage risk."
        ),
    },
    {
        "title": "Earthquake damages key supplier facilities, halting production",
        "body": (
            "An earthquake has damaged key supplier facilities, leading to a temporary "
            "halt in production and potential supply chain disruptions."
        ),
    },
]


class SyntheticConnector:
    """Always-available deterministic disruption scenarios."""

    source_type = SourceType.SYNTHETIC

    def __init__(self, name: str, reliability: float, count: int = 3) -> None:
        self.name = name
        self.reliability = reliability
        self.count = count

    def build_items(self) -> list[RawItem]:
        scenarios = [SCENARIOS[i % len(SCENARIOS)] for i in range(self.count)]
        return [
            RawItem(
                title=s["title"],
                body=s["body"],
                url=None,
                published=None,
                payload={"scenario_index": i, **s},
            )
            for i, s in enumerate(scenarios)
        ]

    def fetch(self) -> list[RawItem]:
        return self.build_items()

    def fallback(self) -> list[RawItem]:
        return self.build_items()
