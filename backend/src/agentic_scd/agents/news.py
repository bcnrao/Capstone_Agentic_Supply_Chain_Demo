from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from agentic_scd.agents.schema import EventAnalysis
from agentic_scd.config import get_settings
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.llm.client import completion

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\b")


def heuristic_analysis(signal: DisruptionSignal) -> EventAnalysis:
    text = signal.text
    entities = []
    for match in ENTITY_RE.findall(text):
        if match not in entities and len(match) > 2:
            entities.append(match)
    hint = signal.severity_hint or "none"
    event_type = "supply_chain_signal"
    lowered = text.lower()
    if any(term in lowered for term in ("typhoon", "storm", "flood", "weather", "earthquake")):
        event_type = "weather_disruption"
    elif any(term in lowered for term in ("strike", "union", "walkout")):
        event_type = "labor_disruption"
    elif any(term in lowered for term in ("tariff", "sanction", "embargo")):
        event_type = "geopolitical_disruption"
    elif any(term in lowered for term in ("defect", "inspection", "recall")):
        event_type = "quality_disruption"
    elif any(term in lowered for term in ("port", "freight", "shipping", "congestion", "delay")):
        event_type = "logistics_disruption"
    return EventAnalysis(
        signal_id=signal.signal_id,
        event_type=event_type,
        entities=entities[:8],
        extracted_region=signal.region,
        severity_hint=str(hint),
        summary=f"{signal.title}. {signal.raw_text[:180]}".strip(),
    )


def llm_analysis(signal: DisruptionSignal) -> EventAnalysis | None:
    settings = get_settings()
    if settings.llm_is_mock:
        return None
    prompt = json.dumps(
        {
            "title": signal.title,
            "body": signal.raw_text,
            "region": signal.region,
            "severity_hint": signal.severity_hint,
        },
        ensure_ascii=False,
    )
    system = "Return JSON only with keys event_type, entities, extracted_region, severity_hint, summary."
    try:
        raw = completion(prompt, system=system, settings=settings, temperature=0)
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start : end + 1])
    except Exception:
        return None
    entities: list[str] = []
    for item in data.get("entities", []):
        value = " ".join(str(item).split())
        if value and value not in entities:
            entities.append(value)
    region = data.get("extracted_region") or signal.region
    summary = " ".join(str(data.get("summary") or "").split()) or f"{signal.title}. {signal.raw_text[:180]}".strip()
    event_type = " ".join(str(data.get("event_type") or "supply_chain_signal").split()) or "supply_chain_signal"
    severity_hint = " ".join(str(data.get("severity_hint") or signal.severity_hint or "none").split()) or "none"
    return EventAnalysis(
        signal_id=signal.signal_id,
        event_type=event_type,
        entities=entities[:8],
        extracted_region=str(region) if region else None,
        severity_hint=severity_hint,
        summary=summary,
    )


def analyze_signal(signal: DisruptionSignal) -> EventAnalysis:
    return llm_analysis(signal) or heuristic_analysis(signal)


def news_node(state: "GraphState") -> dict:
    return {"event_analyses": [analyze_signal(signal) for signal in state.get("new_signals", [])]}
