from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from agentic_scd.agents.schema import Classification, EventAnalysis, WeatherRisk
from agentic_scd.config.settings import DEFAULT_GROQ_MODEL
from agentic_scd.ingestion.schema import DisruptionSignal
from agentic_scd.llm.client import completion
from agentic_scd.rag.retriever import history_retriever, lexical_score

if TYPE_CHECKING:
    from agentic_scd.graph.state import GraphState

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "weather": ("typhoon", "hurricane", "storm", "flood", "flooding", "earthquake", "gale", "weather", "rain", "thunderstorm"),
    "policy": ("tariff", "embargo", "sanction", "border", "policy", "customs", "trade"),
    "geopolitical": ("geopolitical", "conflict", "war", "sanction", "border"),
    "logistics": ("port", "congestion", "shipping", "shipment", "freight", "blockade", "delay", "backlog", "container", "carrier", "route"),
    "raw_material": ("shortage", "supplier", "shutdown", "closure", "outage", "component", "ingredient", "raw material"),
    "demand_shock": ("demand", "surge", "spike", "promotion", "panic", "forecast"),
    "labor_strike": ("strike", "walkout", "union", "labor", "stoppage"),
    "quality": ("defect", "inspection", "recall", "quality", "quarantine", "failure"),
}
HINT_BONUS = {"none": 0.0, "low": 0.5, "moderate": 1.5, "high": 2.5, "severe": 3.5}
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?")
HISTORY_CATEGORY_MAP = {"freight_rate": "logistics", "supply_chain_signal": "other", "runtime_signal": ""}
DISRUPTION_CATEGORIES = set(CATEGORY_KEYWORDS) | {"other", "labor", "natural_disaster"}
DISTILBERT_MODEL = "distilbert-base-uncased"
MODEL_LABELS = list(CATEGORY_KEYWORDS) + ["other"]


def tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def phrase_hit(phrase: str, text: str, words: set[str]) -> bool:
    if " " in phrase or "-" in phrase:
        return phrase in text
    return phrase in words


def normalize_model_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "labour_strike": "labor_strike",
        "labor": "labor",
        "labour": "labor",
        "natural_disaster": "natural_disaster",
        "raw_materials": "raw_material",
        "raw_material": "raw_material",
        "supply_chain": "logistics",
        "transport": "logistics",
        "transportation": "logistics",
        "shipping": "logistics",
    }
    return aliases.get(normalized, normalized)


@lru_cache(maxsize=1)
def _build_distilbert_classifier():
    try:
        from transformers import pipeline
    except Exception:
        return None
    try:
        return pipeline("zero-shot-classification", model=DISTILBERT_MODEL, tokenizer=DISTILBERT_MODEL)
    except Exception:
        return None


def predict_with_model(text: str) -> tuple[str, float]:
    if not text.strip():
        return "other", 0.0
    classifier = _build_distilbert_classifier()
    if classifier is None:
        return "", 0.0
    try:
        result = classifier(text, candidate_labels=MODEL_LABELS)
        label = normalize_model_label(str(result["labels"][0]))
        score = float(result["scores"][0])
        if label not in DISRUPTION_CATEGORIES:
            return "other", score
        return label, score
    except Exception:
        return "", 0.0


def fallback_to_groq(text: str) -> tuple[str, float]:
    prompt = (
        "Classify this supply-chain disruption signal into one of these categories: "
        f"{', '.join(MODEL_LABELS)}. Return JSON with 'category' and 'confidence'.\n\nText: {text}"
    )
    try:
        response = completion(
            prompt,
            system="Classify supply-chain disruption signals.",
            model=DEFAULT_GROQ_MODEL,
        )
        if not response:
            return "", 0.0
        category = ""
        confidence = 0.0
        for token in response.replace("\n", " ").split():
            if token.lower().startswith('"category"') or token.lower().startswith("'category'"):
                continue
        if "category" in response.lower() and "confidence" in response.lower():
            for part in response.split():
                if part.lower().startswith("category"):
                    category = part.split(":", 1)[1].strip().strip('"').strip("'")
                elif part.lower().startswith("confidence"):
                    try:
                        confidence = float(part.split(":", 1)[1].strip().rstrip(","))
                    except ValueError:
                        confidence = 0.0
        if not category:
            return "", 0.0
        normalized = normalize_model_label(category)
        if normalized not in DISRUPTION_CATEGORIES:
            normalized = "other"
        return normalized, max(0.0, min(0.99, confidence))
    except Exception:
        return "", 0.0


_DEFAULT_FALLBACK_TO_GROQ = fallback_to_groq


def classify_signal(signal: DisruptionSignal, analysis: EventAnalysis | None = None, weather: WeatherRisk | None = None) -> Classification:
    text = signal.text.lower()
    words = tokenize(text)
    hits = {
        category: sum(phrase_hit(term, text, words) for term in terms)
        for category, terms in CATEGORY_KEYWORDS.items()
    }
    category = max(hits, key=lambda name: hits[name])
    if hits[category] == 0:
        category = "other"
    elif any(phrase_hit(term, text, words) for term in ("typhoon", "hurricane", "earthquake", "flooding", "thunderstorm", "gale")):
        category = "weather"
    elif "tariff" in words or "embargo" in words or "customs" in words:
        category = "policy"
    elif "port" in words and any(term in words for term in ("strike", "shipping", "shipments", "shipment", "freight", "congestion")):
        category = "logistics"
    elif any(term in words for term in ("strike", "walkout", "union", "stoppage")):
        category = "labor_strike" if "labor" in words or "supplier" in words or "packaging" in words else "labor"
    elif any(term in words for term in ("defect", "quality", "recall")) or "inspection failure" in text:
        category = "quality"
    hit_count = hits.get(category, 0)
    if category == "labor":
        hit_count = max(hit_count, hits.get("labor_strike", 0))

    model_category, model_confidence = predict_with_model(signal.text)
    if model_category and model_confidence >= 0.5:
        category = model_category
    else:
        fallback_category, fallback_confidence = fallback_to_groq(signal.text)
        if fallback_category and fallback_confidence >= 0.5:
            category = fallback_category
        elif model_category:
            category = model_category

    reliability = signal.source_reliability if signal.source_reliability is not None else 0.5
    hint = str(signal.severity_hint or (analysis.severity_hint if analysis else "none")).lower()
    history_category = ""
    history_query = " ".join(part for part in (signal.title, signal.raw_text, signal.region or "", analysis.event_type if analysis else "") if part)
    history_docs = history_retriever().search(history_query, top_k=3)
    for doc in history_docs:
        value = str(doc.metadata.get("category", "")).strip().lower()
        candidate = HISTORY_CATEGORY_MAP.get(value, value)
        if candidate in DISRUPTION_CATEGORIES and lexical_score(history_query, doc) > 0:
            history_category = candidate
            break
    if category == "other" and history_category:
        category = history_category
        hit_count = max(hit_count, 1)
    elif history_category and history_category == category:
        hit_count += 1
    base = 2.0 + 1.05 * hit_count + 2.0 * reliability + HINT_BONUS.get(hint, 0.0)
    if signal.source_type == "WEATHER" and category == "weather":
        base += 1.0
    if weather is not None:
        base += max(0.0, min(2.4, weather.severity_score / 4.0))
        if weather.severity_score >= 6.5:
            category = "weather"
    if category in {"weather", "labor_strike", "labor"} and hit_count >= 2:
        base += 0.8
    severity = round(max(1.0, min(10.0, base)), 2)
    if category == "other":
        severity = min(severity, 3.0)
    risk_score = round(severity / 10.0, 4)
    confidence = round(min(0.98, 0.48 + 0.09 * hit_count + 0.25 * reliability), 4)
    if history_category and history_category == category:
        confidence = round(min(0.99, confidence + 0.07), 4)
    if weather is not None and category == "weather":
        confidence = round(min(0.99, confidence + 0.05), 4)
    if severity > 7:
        level = "HIGH"
        route = "high_path_simulation_first"
    elif severity >= 4:
        level = "MEDIUM"
        route = "full_path"
    else:
        level = "LOW"
        route = "monitor_only"
    weather_note = f", weather severity {weather.severity_score:.1f}" if weather is not None else ""
    history_note = f", history {history_category}" if history_category else ""
    rationale = f"{hit_count} category keyword hits, reliability {reliability:.2f}, hint {hint}{history_note}{weather_note}"
    return Classification(signal_id=signal.signal_id, category=category, risk_score=risk_score, severity=severity, confidence=confidence, risk_level=level, route=route, rationale=rationale)


def classify_node(state: "GraphState") -> dict:
    analyses = {item.signal_id: item for item in state.get("event_analyses", [])}
    weather = {item.signal_id: item for item in state.get("weather_risks", [])}
    rows = [classify_signal(signal, analyses.get(signal.signal_id), weather.get(signal.signal_id)) for signal in state.get("new_signals", [])]
    max_severity = max((row.severity for row in rows), default=0.0)
    if max_severity > 7:
        route = "HIGH severity: simulation is prioritized and mitigation is generated immediately."
    elif max_severity >= 4:
        route = "MEDIUM severity: impact mapping, forecast, simulation, and recommendation all run."
    else:
        route = "LOW severity: event is tracked with a lightweight monitor path."
    return {"classifications": rows, "route": route}
