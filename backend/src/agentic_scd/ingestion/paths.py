"""Filesystem locations the ingestion layer reads/writes.

Resolved relative to the repo root so they work under the local ``uv`` workflow.
``fallback/`` holds committed offline-replay data; ``seed/`` holds committed
historical snapshots the Phase 1c batch loaders read; ``snapshots/`` holds live raw
pulls (gitignored). The root config files (``sources.yaml``, ``lexicon.yaml``) live
at the repo root, matching the structure in specs/data-ingestion.md.
"""

from pathlib import Path

# registry.py lives at <root>/src/agentic_scd/ingestion/ -> parents[3] is the root.
REPO_ROOT = Path(__file__).resolve().parents[3]

FALLBACK_DIR = REPO_ROOT / "data" / "fallback"
# Committed historical snapshots the Phase 1c batch loaders read (offline source of
# truth; committed like FALLBACK_DIR, distinct from the gitignored SNAPSHOT_DIR).
SEED_DIR = REPO_ROOT / "data" / "seed"
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots"

SOURCES_YAML = REPO_ROOT / "sources.yaml"
LEXICON_YAML = REPO_ROOT / "lexicon.yaml"
