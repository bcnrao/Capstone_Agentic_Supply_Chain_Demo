from __future__ import annotations

from agentic_scd.agents.schema import MitigationAction, Recommendation

VALID_URGENCY = {"critical", "high", "medium", "low"}


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def fallback_recommendation(state: dict) -> Recommendation:
    classifications = state.get("classifications", []) or []
    route = clean_text(state.get("route") or "No active disruption route was produced.")
    category = classifications[0].category if classifications else "other"
    action = MitigationAction(
        action=f"Continue monitoring the {category} signal and refresh the disruption review in the next control-tower cycle.",
        urgency="medium",
        expected_impact="Keeps an operator in the loop while preserving a safe default response.",
        owner="Supply chain analyst",
        rationale="Safe default — the pipeline did not produce a structured recommendation, so no simulation-backed rationale is available for this run.",
    )
    return Recommendation(
        actions=[f"[{action.urgency.upper()}] {action.action} Owner: {action.owner}."],
        structured_actions=[action],
        summary=route,
        evidence=[route],
    )


def normalize_action(action: MitigationAction) -> MitigationAction:
    urgency = clean_text(action.urgency).lower() or "medium"
    if urgency not in VALID_URGENCY:
        urgency = "medium"
    text = clean_text(action.action) or "Review the disruption signal with the control tower."
    expected = clean_text(action.expected_impact) or "Preserves a valid mitigation plan for the operator."
    owner = clean_text(action.owner) or "Supply chain analyst"
    rationale = clean_text(action.rationale)
    return MitigationAction(action=text, urgency=urgency, expected_impact=expected, owner=owner, rationale=rationale)


def output_guardrail_node(state: dict) -> dict:
    recommendation = state.get("recommendation")
    if not recommendation:
        recommendation = fallback_recommendation(state)
    structured = [normalize_action(item) for item in recommendation.structured_actions[:6]]
    if not structured and recommendation.actions:
        structured = [
            MitigationAction(
                action=clean_text(str(recommendation.actions[0])),
                urgency="medium",
                expected_impact="Keeps a baseline mitigation plan active.",
                owner="Supply chain analyst",
            )
        ]
    if not structured:
        recommendation = fallback_recommendation(state)
        structured = recommendation.structured_actions
    actions = [f"[{item.urgency.upper()}] {item.action} Owner: {item.owner}." for item in structured]
    evidence: list[str] = []
    for item in recommendation.evidence:
        text = clean_text(item)
        if text and text not in evidence:
            evidence.append(text)
    summary = clean_text(recommendation.summary) or fallback_recommendation(state).summary
    if len(summary) > 280:
        summary = summary[:277].rsplit(" ", 1)[0].rstrip("., ") + "..."
    return {
        "recommendation": Recommendation(
            actions=actions,
            structured_actions=structured,
            summary=summary,
            evidence=evidence[:6],
        )
    }
