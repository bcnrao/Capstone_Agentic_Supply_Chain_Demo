"""Calibration harness for the Impact agent's "no material impact" gate.

The Impact agent (agents/impact.py) decides whether a disruption touches our
network using a hybrid gate: a deterministic structured match (region / product /
place tokens from the Network KB) plus a fuzzy RAG backstop (cosine distance to
the nearest supplier, cutoff = GATE_DISTANCE).

This script prints, for a labelled set of sample events, what the structured
matcher decides and the best RAG cosine distance — so the GATE_DISTANCE cutoff
and the REGION_ALIASES list can be re-tuned when the Network KB is enriched.

Run:  cd backend && uv run python scripts/calibrate_impact_gate.py
Labels: E = should impact us, N = should not.
"""
from __future__ import annotations

from agentic_scd.agents.impact import GATE_DISTANCE, _structured_hits
from agentic_scd.rag.retriever import network_retriever

SAMPLES = [
    ("E", "Typhoon approaching Shanghai port, container handling suspended"),
    ("E", "New tariff on imported cosmetic ingredients in North America"),
    ("E", "Port workers strike in Rotterdam halts container operations"),
    ("E", "Cosmetics supplier in Mumbai faces a production shutdown"),
    ("E", "Los Angeles port congestion worsens amid backlog"),
    ("E", "Vietnam factory fire disrupts fragrance and cosmetics production"),
    ("N", "Australian iron ore miners go on strike at Port Hedland"),
    ("N", "US Federal Reserve raises interest rates by 25 basis points"),
    ("N", "Tech giant launches new flagship smartphone"),
    ("N", "Brazil coffee harvest hit by severe drought"),
    ("N", "Suez Canal briefly blocked by a grounded cargo ship"),
    ("N", "Global semiconductor shortage continues to affect the auto industry"),
    # Implicit on-network events — no exact region/product/place token, so these
    # exercise the *fuzzy* backstop against the enriched supplier descriptions /
    # materials (they were the "shows no impact" false-negatives before enrichment).
    ("E", "Titanium dioxide export curbs raise pigment and colorant costs worldwide"),
    ("E", "Aroma compound supplier halts shipments, squeezing perfume bottlers"),
    ("E", "Hyaluronic acid and peptide serum ingredients in short supply"),
    ("E", "Coconut and argan oil prices surge for shampoo and conditioner makers"),
    ("E", "Trans-Pacific container backlog delays consumer-goods imports to the US West Coast"),
    # Implicit off-network noise — must stay above the gate.
    ("N", "Titanium ore miners strike in Australia over pay dispute"),
    ("N", "Steel and cement demand slumps amid a construction downturn"),
]


def main() -> None:
    net = network_retriever()
    print(f"GATE_DISTANCE = {GATE_DISTANCE}   (cosine distance; lower = closer)\n")
    print(f"{'lbl':3s} {'structured?':11s} {'RAGdist':7s}  decision  event")
    print("-" * 96)
    for label, text in SAMPLES:
        place, product, region = _structured_hits(text, None, None)
        structured = bool(place or product or region)
        scored = net.search_scored(text, top_k=1, kind="suppliers")
        dist = scored[0][1] if scored else None
        fuzzy = dist is not None and dist < GATE_DISTANCE
        material = structured or fuzzy
        print(f"{label:3s} {('MATCH' if structured else 'no-match'):11s} "
              f"{(f'{dist:.3f}' if dist is not None else '  n/a'):7s}  "
              f"{'IMPACT ' if material else 'ignore ':8s}  {text[:52]}")


if __name__ == "__main__":
    main()
