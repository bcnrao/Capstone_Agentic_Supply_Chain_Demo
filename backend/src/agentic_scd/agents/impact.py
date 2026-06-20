"""Impact-map stub — hard-coded category -> affected network entities, per signal.

The simplest real thing: a fixed lookup from disruption category to the suppliers,
lanes, and facilities in *our* network it would touch. Phase 4 replaces this with RAG
over the internal supply-chain knowledge base (Chroma) behind the same ``impact_node``
signature.
"""

from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification, ImpactMap

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

# Category -> affected suppliers / lanes / facilities (the Phase 4 KB replaces this).
IMPACT_BY_CATEGORY: dict[str, list[str]] = {
    "labor": ["Port of Los Angeles", "Trans-Pacific lane", "West Coast DC"],
    "natural_disaster": [
        "Taiwan chip supplier",
        "Trans-Pacific lane",
        "Shenzhen assembly facility",
    ],
    "logistics": ["Port of Rotterdam", "EU inbound lane", "Central warehouse"],
    "policy": ["Tariff-exposed supplier", "Cross-border lane", "Procurement hub"],
    "supply": ["Tier-1 component supplier", "Inbound lane", "Manufacturing plant"],
    "other": ["General supplier", "Primary lane"],
}


def map_impact(classification: Classification) -> ImpactMap:
    """Look up the affected entities for one classified signal."""
    entities = IMPACT_BY_CATEGORY.get(
        classification.category, IMPACT_BY_CATEGORY["other"]
    )
    return ImpactMap(
        signal_id=classification.signal_id,
        affected_entities=list(entities),
    )


def impact_node(state: "GraphState") -> dict:
    """Map each classified signal to the parts of our network it touches."""
    classifications = state.get("classifications", [])
    return {"impacts": [map_impact(c) for c in classifications]}
