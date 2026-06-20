# Phase 1c — Batch loaders & retention · Plan

Numbered task groups. Each is independently reviewable; the order respects dependencies —
committed seed data + paths/config come before the loaders that read them, the loaders and
retention come before the CLI that runs them, and tests/docs close it out. Scope and
decisions in [[requirements]]; success criteria in [[validation]]. The loaders reuse the
normalize → dedupe → persist tail from [[data-ingestion]].

---

## 1. Seed data, paths & config
1.1 `data/seed/` — commit **small trimmed** snapshots: a Freightos Baltic Index sample
    (freight-rate rows) and a Kaggle SupplyChainNet extract (historical disruption/demand
    rows). Just enough to demo offline; document provenance in a short `data/seed/README.md`.
1.2 `ingestion/paths.py` — add `SEED_DIR = REPO_ROOT / "data" / "seed"` (committed, like
    `FALLBACK_DIR`; distinct from the gitignored `snapshots/`).
1.3 `config.Settings` — add env-driven knobs with sensible defaults, matching the existing
    `INGEST_*` style: `batch_enabled`, `retention_rejected_ttl_days`,
    `retention_signals_ttl_days` (and an enable flag for retention).

## 2. Batch loaders (`ingestion/batch/`)
Each loader reads a committed snapshot → builds `DisruptionSignal`s → the **existing**
`ingest_signals` tail (normalize/dedupe/persist), idempotent on `dedup_hash`.
2.1 `ingestion/batch/freightos.py` — parse the Freightos snapshot rows into `RawItem`s →
    `normalize` → `DisruptionSignal`s with a **batch/cached** `source_type`; emit freight-rate
    baselines. Reuse a synthetic/cached `Connector`-style source descriptor for `normalize`.
2.2 `ingestion/batch/kaggle.py` — parse the SupplyChainNet extract into historical
    disruption/demand `DisruptionSignal`s (demand baselines + persisted **KB-history**
    records — **persist only, no embedding**; see [[requirements]] vector-DB boundary).
2.3 `ingestion/batch/__init__.py` — a small `load_batch(conn, settings) -> BatchSummary`
    that runs the enabled loaders once and tallies loaded/kept/dropped/persisted per source
    (mirrors `collect`'s `CollectSummary` shape).

## 3. Retention / TTL (`ingestion/retention.py`)
3.1 `prune_seen_rejected(conn, ttl_days)` — delete `seen_rejected` rows whose
    `first_seen_at` is older than the TTL.
3.2 `prune_signals(conn, ttl_days)` — delete **stale accepted** signals only
    (`status='done'` past `created_at` + TTL); **never** touch `new`/`processing` rows the
    pipeline still needs. Return counts pruned.
3.3 `run_retention(conn, settings) -> RetentionSummary` — orchestrate both, guarded so it is
    a clean no-op with no DB.

## 4. On-demand CLI (`agentic-scd-batch`)
4.1 `ingestion/batch_cli.py` (or `ingestion/batch/cli.py`) — `main()` opens a DB connection
    (graceful `None` when unreachable), runs `load_batch` and `run_retention`, and prints a
    concise summary (per-source loaded/persisted; rows pruned; `path: live|offline`). Mirror
    `collect.py`'s `print_summary` layout.
4.2 `pyproject.toml` — register `agentic-scd-batch = "agentic_scd.ingestion.batch_cli:main"`.
    Flags (or env) select **load**, **retain**, or both.

## 5. Tests (offline, no DB/network)
5.1 Per-loader: a committed seed sample parses into the expected `DisruptionSignal`s
    (counts, `source_type`, key fields), and a **second run is idempotent** (no duplicate
    persists) — using an in-memory/None-conn path or a fake conn, matching the Phase 1 test
    style.
5.2 Retention: with a small fixture set, `prune_*` removes **only** the intended rows
    (old `seen_rejected`, `done`-past-TTL signals) and **preserves** `new`/`processing` and
    in-window rows.
5.3 CLI smoke: `main()` runs fully offline (no DB) without crashing and prints a summary;
    any DB-touching assertions skip cleanly.
5.4 `ruff check` + `ruff format --check` clean across the tree.

## 6. Docs & wrap-up
6.1 README "Batch loaders & retention (Phase 1c)" section: `uv run agentic-scd-batch`
    (offline seed + retention), what each loader lands and that it is **persisted, not
    embedded** (Phase 4/7 vectorize), and the TTL knobs.
6.2 Mark Phase 1c complete in [[roadmap]] once green; confirm all [[validation]] criteria
    pass; open a PR from `phase-1c-batch-loaders-retention` into `main`.
