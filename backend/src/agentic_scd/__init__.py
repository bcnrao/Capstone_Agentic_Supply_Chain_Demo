"""Agentic Supply Chain Disruption Predictor & Simulation Engine.

Phase 0 scaffolding: an importable package with a thin LLM wrapper, the shared
``DisruptionSignal`` schema, a typed LangGraph state, and a single stub node wired
into a runnable graph. Later phases fill the ``ingestion``, ``graph``, ``llm`` and
``config`` subpackages with real logic (see ``specs/roadmap.md``).
"""

__version__ = "0.1.0"
