"""Always-demoable seed node.

The walking skeleton must show a full end-to-end result even with no DB and no network
(per the mission's always-demoable / graceful-degradation principle). When ingestion
yields no signals, this node injects one deterministic synthetic ``DisruptionSignal``
(reusing the Phase 1 synthetic connector + normalizer) so the downstream stubs always
have input. When real signals are present it is a no-op.
"""

from typing import TYPE_CHECKING

from agentic_scd.ingestion.connectors.synthetic import SyntheticConnector
from agentic_scd.ingestion.normalize import normalize

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState


def seed_node(state: "GraphState") -> dict:
    """Inject one synthetic signal iff this run has none (else no-op)."""
    if state.get("new_signals"):
        return {}
    connector = SyntheticConnector(name="demo_seed", reliability=0.6, count=1)
    signals = [normalize(item, connector) for item in connector.fetch()]
    return {"new_signals": signals}
