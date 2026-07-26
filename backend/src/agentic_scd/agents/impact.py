from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification, EventAnalysis, ImpactMap, WeatherRiskAssessment
from agentic_scd.config import get_settings
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.llm.client import completion
from agentic_scd.rag.retriever import network_retriever

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

# Trade lanes served out of each monitored weather hub, used to ground a weather
# disruption to the parts of our network it most directly threatens.
HUB_LANES = {
    "Port of Shanghai": ["Shanghai-Los Angeles"],
    "Port of Rotterdam": ["Mumbai-Rotterdam", "Rotterdam-New York"],
    "Port of Los Angeles": ["Los Angeles-Dallas"],
}

# Keyword nudges added to the RAG query per disruption category.
CATEGORY_HINTS = {
    "weather": ["port", "warehouse", "Sea"],
    "natural_disaster": ["supplier", "port"],
    "labor": ["port", "warehouse"],
    "labor_strike": ["port", "warehouse"],
    "logistics": ["lane", "Sea", "port"],
    "policy": ["supplier", "lane", "tariff"],
    "geopolitical": ["supplier", "lane"],
    "raw_material": ["supplier", "products"],
    "quality": ["supplier", "products"],
    "demand_shock": ["warehouse", "products"],
}

# Cosine-distance cutoff for the fuzzy RAG backstop — a signal whose nearest
# supplier is farther than this (and matched no structured token) is treated as
# "no material impact". Calibrated on the network KB (see calibrate_impact_gate).
GATE_DISTANCE = 0.65

# Region phrasings in the news that map onto a network region.
REGION_ALIASES = {
    "north america": "usa", "united states": "usa", "american": "usa",
    "chinese": "china", "indian": "india", "dutch": "netherlands", "vietnamese": "vietnam",
}

# Facility-name words to strip when deriving a facility's city token.
_FACILITY_TYPE_WORDS = {
    "port", "consolidation", "hub", "dc", "import", "blending", "plant",
    "warehouse", "distribution", "center", "centre", "terminal",
}


@lru_cache(maxsize=1)
def _network() -> dict:
    """The Network KB. Cached; enrichment of network.json needs a restart."""
    try:
        return json.loads((SEED_DIR / "network.json").read_text(encoding="utf-8"))
    except Exception:
        return {"suppliers": [], "facilities": [], "lanes": []}


@lru_cache(maxsize=1)
def _vocab() -> tuple[frozenset, frozenset, frozenset]:
    """Matchable vocabulary derived from the Network KB: regions, product lines,
    and place tokens (lane endpoints + facility cities)."""
    net = _network()
    regions = {str(s.get("region", "")).lower() for s in net.get("suppliers", [])}
    regions |= {str(f.get("region", "")).lower() for f in net.get("facilities", [])}
    regions.discard("")
    products = {str(p).lower() for s in net.get("suppliers", []) for p in s.get("products", [])}
    places: set[str] = set()
    for lane in net.get("lanes", []):
        for part in str(lane.get("name", "")).lower().split("-"):
            if part.strip():
                places.add(part.strip())
    for fac in net.get("facilities", []):
        words = [w for w in str(fac.get("name", "")).lower().split() if w not in _FACILITY_TYPE_WORDS]
        if words:
            places.add(" ".join(words))
    return frozenset(regions), frozenset(products), frozenset(places)


def _dedup(items) -> list:
    return list(dict.fromkeys(x for x in items if x))


def _structured_hits(text: str, region: str | None, weather: WeatherRiskAssessment | None):
    """Which network regions / products / places does this event reference?"""
    regions, products, places = _vocab()
    haystack = text.lower()
    if region:
        haystack += " " + region.lower()
    if weather is not None and weather.hub_port:
        haystack += " " + str(weather.hub_port).lower()
    place_hits = {p for p in places if p in haystack}
    product_hits = {p for p in products if p in haystack}
    region_hits = {r for r in regions if r in haystack}
    region_hits |= {REGION_ALIASES[a] for a in REGION_ALIASES if a in haystack}
    return place_hits, product_hits, region_hits


def _candidate_nodes(place_hits, product_hits, region_hits, weather):
    """Turn structured hits into candidate supplier / facility rows + matched lanes."""
    net = _network()
    hub_lanes = HUB_LANES.get(weather.hub_port, []) if weather is not None else []
    lane_hits = {
        lane["name"] for lane in net.get("lanes", [])
        if any(p in lane["name"].lower() for p in place_hits)
    } | set(hub_lanes)
    suppliers = [
        s for s in net.get("suppliers", [])
        if str(s.get("region", "")).lower() in region_hits
        or product_hits & {str(p).lower() for p in s.get("products", [])}
        or s.get("primary_lane") in lane_hits
    ]
    facilities = [
        f for f in net.get("facilities", [])
        if str(f.get("region", "")).lower() in region_hits
        or set(f.get("lanes", [])) & lane_hits
        or any(p in f.get("name", "").lower() for p in place_hits)
    ]
    return suppliers, facilities, lane_hits


def map_impact(
    signal: DisruptionSignal,
    classification: Classification,
    weather: WeatherRiskAssessment | None = None,
    event_analysis: EventAnalysis | None = None,
) -> ImpactMap:
    net = _network()
    text = signal.text
    if event_analysis is not None and event_analysis.entities:
        text = f"{text} {' '.join(event_analysis.entities)}"

    place_hits, product_hits, region_hits = _structured_hits(text, signal.region, weather)
    sup_rows, fac_rows, lane_hits = _candidate_nodes(place_hits, product_hits, region_hits, weather)

    # RAG: rank suppliers semantically + get the fuzzy-backstop distance.
    query = " ".join(filter(None, [
        signal.text, classification.category,
        *CATEGORY_HINTS.get(classification.category, []), signal.region or "",
    ]))
    scored = network_retriever().search_scored(query, top_k=5, kind="suppliers")
    best_dist = scored[0][1] if scored else None

    structured = bool(place_hits or product_hits or region_hits)
    fuzzy = best_dist is not None and best_dist < GATE_DISTANCE

    # --- the "don't care" gate ---
    if not structured and not fuzzy:
        reason = f"No monitored network entity is materially exposed to this {classification.category} event"
        if best_dist is not None:
            reason += f" (nearest supplier distance {best_dist:.2f} > {GATE_DISTANCE:.2f})"
        return ImpactMap(signal_id=signal.signal_id, reasoning=reason + ".")

    # --- pick affected suppliers ---
    if sup_rows:  # structured candidates, ordered by RAG rank
        rank = {str(doc.metadata.get("name")): i for i, (doc, _) in enumerate(scored)}
        sup_rows = sorted(sup_rows, key=lambda s: rank.get(s["name"], 999))[:4]
    else:  # fuzzy path — RAG-nearest suppliers under the gate
        near = [str(doc.metadata.get("name")) for doc, dist in scored if dist < GATE_DISTANCE][:3]
        sup_rows = [s for s in net.get("suppliers", []) if s["name"] in near]

    suppliers = [s["name"] for s in sup_rows]
    products = _dedup(str(p) for s in sup_rows for p in s.get("products", []))
    lanes = _dedup([s.get("primary_lane") for s in sup_rows] + list(lane_hits))

    # --- facilities: structured candidates, else those serving the affected lanes ---
    if not fac_rows:
        fac_rows = [f for f in net.get("facilities", []) if set(f.get("lanes", [])) & set(lanes)]
    facilities = [f["name"] for f in fac_rows]
    lanes = _dedup(lanes + [lane for f in fac_rows for lane in f.get("lanes", [])])

    if weather is not None and weather.hub_port in HUB_LANES:
        lanes = _dedup(HUB_LANES[weather.hub_port] + lanes)

    suppliers, lanes = _dedup(suppliers)[:4], _dedup(lanes)[:5]
    facilities, products = _dedup(facilities)[:4], products[:5]
    reasoning = (
        f"Mapped {classification.category} risk to {len(suppliers)} supplier(s), "
        f"{len(lanes)} lane(s), {len(facilities)} facility node(s), {len(products)} product line(s)."
    )
    return ImpactMap(
        signal_id=signal.signal_id,
        affected_suppliers=suppliers,
        affected_lanes=lanes,
        affected_facilities=facilities,
        product_categories=products,
        retrieved_context=[doc.text for doc, _ in scored[:4]],
        reasoning=reasoning,
    )


def _deterministic_impact_summary(classifications: list[Classification], impacts: list[ImpactMap]) -> str:
    if not impacts:
        return "No impact assessment available."
    categories = {c.signal_id: c.category for c in classifications}
    material = [i for i in impacts if i.affected_entities]
    dontcare = [i for i in impacts if not i.affected_entities]
    headline = f"{len(material)} event(s) materially impact the network"
    if dontcare:
        headline += f"; {len(dontcare)} are don't-cares outside our footprint"
    lines = [headline + "."]
    for imp in material:
        cat = categories.get(imp.signal_id, "event")
        suppliers = ", ".join(imp.affected_suppliers) or "network nodes"
        products = ", ".join(imp.product_categories)
        product_txt = f" (products: {products})" if products else ""
        lines.append(
            f"- {cat} → {suppliers}{product_txt}; "
            f"{len(imp.affected_lanes)} lane(s), {len(imp.affected_facilities)} facility node(s)."
        )
    return "\n".join(lines)


def impact_summary(classifications: list[Classification], impacts: list[ImpactMap]) -> str:
    """Operator-facing summary of what is impacted. LLM-written when a real model
    is configured; falls back to the deterministic template otherwise."""
    deterministic = _deterministic_impact_summary(classifications, impacts)
    settings = get_settings()
    material = [i for i in impacts if i.affected_entities]
    if settings.llm_is_mock or not material:
        return deterministic
    categories = {c.signal_id: c.category for c in classifications}
    facts = {
        "materially_impacted": [
            {
                "category": categories.get(i.signal_id, "event"),
                "suppliers": i.affected_suppliers,
                "products": i.product_categories,
                "lanes": i.affected_lanes,
                "facilities": i.affected_facilities,
            }
            for i in material
        ],
        "dont_care_count": sum(1 for i in impacts if not i.affected_entities),
    }
    system = (
        "You summarize supply-chain impact analysis for an operator. Given the JSON facts, "
        "write 2-4 short plain-text sentences describing what is materially impacted "
        "(suppliers, product lines, lanes, facilities). Only if dont_care_count > 0, add one "
        "short sentence noting how many events are don't-cares outside the monitored network; "
        "if dont_care_count is 0, do NOT mention don't-cares. Never invent entities not present "
        "in the facts. No preamble, no markdown headings."
    )
    try:
        out = " ".join((completion(json.dumps(facts), system=system, settings=settings, temperature=0) or "").split())
        return out or deterministic
    except Exception:
        return deterministic


def impact_node(state: "GraphState") -> dict:
    signals = {signal.signal_id: signal for signal in state.get("new_signals", [])}
    weather_map = {item.signal_id: item for item in state.get("weather_risks", [])}
    analysis_map = {item.signal_id: item for item in state.get("event_analyses", [])}
    impacts = []
    for item in state.get("classifications", []):
        if item.severity < 3:
            continue
        signal = signals.get(item.signal_id)
        if signal is None:
            impacts.append(ImpactMap(signal_id=item.signal_id, reasoning="No signal payload available to map impact."))
            continue
        impacts.append(map_impact(signal, item, weather_map.get(item.signal_id), analysis_map.get(item.signal_id)))
    return {"impacts": impacts, "impact_summary": impact_summary(state.get("classifications", []), impacts)}
