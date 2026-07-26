from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification, ImpactMap, MitigationAction, Recommendation, Simulation
from agentic_scd.config import get_settings
from agentic_scd.llm.client import completion
from agentic_scd.rag.retriever import mitigation_retriever

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

OWNER_BY_CATEGORY = {
    "weather": "Logistics lead",
    "natural_disaster": "Logistics lead",
    "labor": "Transportation manager",
    "labor_strike": "Transportation manager",
    "logistics": "Control tower analyst",
    "policy": "Procurement lead",
    "geopolitical": "Procurement lead",
    "raw_material": "Sourcing manager",
    "demand_shock": "Demand planner",
    "quality": "Supplier quality engineer",
    "other": "Supply chain analyst",
}
PLAYBOOK_CATEGORY = {"labor": "labor_strike", "policy": "geopolitical", "natural_disaster": "weather"}


def urgency(classification: Classification, simulation: Simulation) -> str:
    if classification.severity > 7 or simulation.stockout_probability >= 0.6:
        return "critical"
    if classification.severity >= 5 or simulation.stockout_probability >= 0.35:
        return "high"
    return "medium"


def parse_json_payload(raw: str):
    start_dict = raw.find("{")
    start_list = raw.find("[")
    if start_dict < 0 and start_list < 0:
        return None
    if start_list >= 0 and (start_dict < 0 or start_list < start_dict):
        end = raw.rfind("]")
        return json.loads(raw[start_list : end + 1]) if end > start_list else None
    end = raw.rfind("}")
    return json.loads(raw[start_dict : end + 1]) if end > start_dict else None


def llm_recommendation(classifications: list[Classification], impacts: list[ImpactMap], simulation: Simulation, evidence: list[str]) -> tuple[list[MitigationAction], list[str]] | None:
    settings = get_settings()
    if settings.llm_is_mock:
        return None
    payload = {
        "classifications": [item.model_dump(mode="json") for item in classifications],
        "impacts": [item.model_dump(mode="json") for item in impacts],
        "simulation": simulation.model_dump(mode="json"),
        "playbook_evidence": evidence,
    }
    system = "Return JSON only with a top-level key actions. Each action must include action, urgency, expected_impact, owner, evidence."
    try:
        raw = completion(json.dumps(payload, ensure_ascii=False), system=system, settings=settings, temperature=0)
        data = parse_json_payload(raw)
    except Exception:
        return None
    if data is None:
        return None
    rows = data.get("actions", data) if isinstance(data, dict) else data
    structured: list[MitigationAction] = []
    llm_evidence: list[str] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        action = " ".join(str(row.get("action", "")).split())
        if not action:
            continue
        level = " ".join(str(row.get("urgency", "high")).split()).lower() or "high"
        expected = " ".join(str(row.get("expected_impact", "Reduces disruption exposure.")).split()) or "Reduces disruption exposure."
        owner = " ".join(str(row.get("owner", "Supply chain analyst")).split()) or "Supply chain analyst"
        citation = " ".join(str(row.get("evidence", "")).split())
        structured.append(MitigationAction(action=action, urgency=level, expected_impact=expected, owner=owner))
        if citation:
            llm_evidence.append(citation)
    if not structured:
        return None
    return structured, llm_evidence


def build_recommendation(classifications: list[Classification], impacts: list[ImpactMap], simulation: Simulation) -> Recommendation:
    # No affected network entities => no material impact: nothing to mitigate,
    # just keep watching the event.
    affected = sum(len(item.affected_entities) for item in impacts)
    if classifications and affected <= 0:
        category = max(classifications, key=lambda c: c.severity).category
        action = MitigationAction(
            action=f"Monitor only — this {category} event does not materially impact the monitored network. Keep watching for escalation.",
            urgency="low",
            expected_impact="No action required while the event stays outside our supplier, lane and facility footprint.",
            owner="Control tower analyst",
        )
        return Recommendation(
            actions=[f"[{action.urgency.upper()}] {action.action} Owner: {action.owner}."],
            structured_actions=[action],
            summary=f"No material impact to the monitored network from this {category} event — monitoring only.",
            evidence=[],
            generation_mode="no_material_impact",
        )

    structured: list[MitigationAction] = []
    evidence: list[str] = []
    categories = list(dict.fromkeys(item.category for item in classifications)) or ["other"]
    max_by_category = {category: max((item for item in classifications if item.category == category), key=lambda item: item.severity, default=None) for category in categories}
    for category in categories:
        classification = max_by_category.get(category)
        search_category = PLAYBOOK_CATEGORY.get(category, category)
        docs = mitigation_retriever().search(search_category, top_k=2, category=search_category)
        if not docs:
            docs = mitigation_retriever().search(category, top_k=2)
        if docs:
            chosen = docs[0]
            meta = chosen.metadata
            action = str(meta.get("action", "Review supplier exposure and raise safety stock."))
            if category == "logistics" and "freight" not in action.lower():
                action = f"{action} Use controlled emergency freight only for top SKUs."
            expected = str(meta.get("expected_effect", "Reduces disruption exposure."))
            evidence.append(f"{meta.get('title', chosen.doc_id)}: {expected}")
        else:
            action = "Review supplier exposure, reserve safety stock, and prepare an alternate route."
            expected = "Creates a controlled response while more data arrives."
        if category == "logistics" and "freight" not in action.lower():
            action = f"Use the freight mitigation playbook: {action}"
        level = urgency(classification, simulation) if classification else "medium"
        owner = OWNER_BY_CATEGORY.get(category, "Supply chain analyst")
        structured.append(MitigationAction(action=action, urgency=level, expected_impact=expected, owner=owner))
    generation_mode = "deterministic_playbook"
    llm_result = llm_recommendation(classifications, impacts, simulation, evidence)
    if llm_result is not None:
        structured, llm_evidence = llm_result
        for item in evidence + llm_evidence:
            if item and item not in llm_evidence:
                llm_evidence.append(item)
        evidence = llm_evidence
        generation_mode = "llm_playbook"
    if simulation.stockout_probability >= 0.5:
        structured.insert(0, MitigationAction(action="Open a daily disruption war-room until stockout probability drops below 35 percent.", urgency="critical", expected_impact="Keeps cross-functional decisions synchronized during the highest-risk window.", owner="Supply chain director"))
    actions = [f"[{item.urgency.upper()}] {item.action} Owner: {item.owner}." for item in structured]
    impacted = sum(len(item.affected_entities) for item in impacts)
    summary = f"{len(actions)} ranked actions for {len(categories)} risk category(ies), {impacted} affected network node(s), stockout probability {simulation.stockout_probability:.0%}, expected revenue impact {simulation.revenue_impact:,.0f}."
    return Recommendation(actions=actions, structured_actions=structured, summary=summary, evidence=evidence, generation_mode=generation_mode)


def recommend_node(state: "GraphState") -> dict:
    simulation = state.get("simulation") or Simulation(stockout_probability=0.0)
    return {"recommendation": build_recommendation(state.get("classifications", []), state.get("impacts", []), simulation)}
