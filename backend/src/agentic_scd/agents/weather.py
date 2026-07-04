from __future__ import annotations

from typing import TYPE_CHECKING

from agentic_scd.agents.schema import EventAnalysis, WeatherRisk
from agentic_scd.ingestion.schema import DisruptionSignal

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

WEATHER_TERMS = ("typhoon", "hurricane", "storm", "flood", "rain", "thunderstorm", "gale", "weather", "earthquake", "cyclone")
SEVERITY_SCORE = {"none": 1.0, "low": 2.5, "moderate": 5.5, "high": 7.4, "severe": 9.0}


def location_name(signal: DisruptionSignal) -> str | None:
    if signal.location and signal.location.hub_port:
        return signal.location.hub_port
    text = signal.text
    for token in ("port", "harbor", "hub"):
        lowered = text.lower()
        if token not in lowered:
            continue
        idx = lowered.find(token)
        start = max(0, idx - 24)
        return " ".join(text[start : idx + len(token)].split()).strip(" ,.")
    return None


def build_weather_risk(signal: DisruptionSignal, analysis: EventAnalysis | None = None) -> WeatherRisk | None:
    text = signal.text.lower()
    is_weather = signal.source_type == "WEATHER" or any(term in text for term in WEATHER_TERMS)
    if analysis and "weather" in analysis.event_type.lower():
        is_weather = True
    if not is_weather:
        return None
    payload = signal.raw_payload or {}
    response = payload.get("response", {})
    daily = response.get("daily", {})
    wind = (daily.get("wind_speed_10m_max") or [None])[0]
    precip = (daily.get("precipitation_sum") or [None])[0]
    hint = str(payload.get("severity_hint") or signal.severity_hint or (analysis.severity_hint if analysis else "moderate")).lower()
    score = SEVERITY_SCORE.get(hint, 5.0)
    if wind is not None:
        score = max(score, min(9.5, 2.0 + float(wind) / 12.0))
    if precip is not None:
        score = max(score, min(9.5, 2.0 + float(precip) / 8.0))
    if any(term in text for term in ("shutdown", "suspend", "flooding", "blocked", "closures")):
        score = min(10.0, score + 0.8)
    factor = round(min(1.0, max(0.15, score / 10.0)), 4)
    region = signal.region or (analysis.extracted_region if analysis else None)
    hub = location_name(signal)
    summary = analysis.summary if analysis and analysis.summary else signal.title
    return WeatherRisk(
        signal_id=signal.signal_id,
        region=region,
        hub=hub,
        alert_level=hint.upper(),
        severity_score=round(score, 2),
        wind_kph=float(wind) if wind is not None else None,
        precipitation_mm=float(precip) if precip is not None else None,
        disruption_factor=factor,
        monitoring_window_days=max(2, int(round(2 + score / 1.8))),
        summary=summary,
    )


def weather_node(state: "GraphState") -> dict:
    analyses = {item.signal_id: item for item in state.get("event_analyses", []) or []}
    rows = []
    for signal in state.get("new_signals", []) or []:
        risk = build_weather_risk(signal, analyses.get(signal.signal_id))
        if risk is not None:
            rows.append(risk)
    return {"weather_risks": rows}
