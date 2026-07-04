from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from agentic_scd.db import connect, init_db
from agentic_scd.ingestion.paths import SEED_DIR
from agentic_scd.ingestion.sqlutil import execute

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]+")


@dataclass(frozen=True)
class Document:
    doc_id: str
    text: str
    metadata: dict


def tokens(text: str) -> set[str]:
    return {item.lower() for item in TOKEN_RE.findall(text)}


def score(query: str, document: Document) -> float:
    q = tokens(query)
    d = tokens(document.text)
    if not q or not d:
        return 0.0
    overlap = len(q & d)
    meta_tokens = tokens(
        " ".join(
            str(document.metadata.get(key, ""))
            for key in ("category", "kind", "region", "name", "title", "route")
        )
    )
    phrase_bonus = 0.2 if query.lower().strip() and query.lower() in document.text.lower() else 0.0
    metadata_bonus = 0.15 if q & meta_tokens else 0.0
    return overlap / math.sqrt(len(q) * len(d)) + phrase_bonus + metadata_bonus


class LocalRetriever:
    def __init__(self, documents: list[Document] | Callable[[], list[Document]]) -> None:
        self._documents = documents

    @property
    def documents(self) -> list[Document]:
        if callable(self._documents):
            return self._documents()
        return self._documents

    def search(self, query: str, top_k: int = 4, category: str | None = None) -> list[Document]:
        docs = self.documents
        if category:
            preferred = [doc for doc in docs if doc.metadata.get("category") == category]
            if preferred:
                docs = preferred
        ranked = sorted(docs, key=lambda doc: score(query, doc), reverse=True)
        return [doc for doc in ranked if score(query, doc) > 0][:top_k]


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def row_value(row, key: str, index: int):
    if isinstance(row, tuple):
        return row[index]
    return row[key]


def parse_json(value):
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)


def network_documents() -> list[Document]:
    data = read_json(SEED_DIR / "network.json", {})
    docs: list[Document] = []
    for section in ("suppliers", "facilities", "lanes"):
        for idx, row in enumerate(data.get(section, [])):
            text = " ".join(str(value) for value in row.values())
            docs.append(Document(doc_id=f"{section}-{idx}", text=text, metadata={"kind": section, **row}))
    return docs


def playbook_documents() -> list[Document]:
    rows = read_json(SEED_DIR / "playbooks.json", [])
    return [
        Document(
            doc_id=f"playbook-{idx}",
            text=" ".join([row.get("title", ""), row.get("action", ""), " ".join(row.get("best_for", [])), row.get("expected_effect", "")]),
            metadata={"kind": "playbook", **row},
        )
        for idx, row in enumerate(rows)
    ]


def synthetic_history_documents() -> list[Document]:
    path = SEED_DIR / "synthetic_disruption_events.jsonl"
    if not path.exists():
        return []
    docs: list[Document] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        docs.append(
            Document(
                doc_id=f"synthetic-{idx}",
                text=" ".join([str(row.get("description", "")), str(row.get("region", "")), str(row.get("label", ""))]),
                metadata={"kind": "history", "category": row.get("label", "other"), **row},
            )
        )
    return docs


def kaggle_history_documents() -> list[Document]:
    data = read_json(SEED_DIR / "kaggle_supplychainnet.json", {})
    docs: list[Document] = []
    for idx, row in enumerate(data.get("records", [])):
        if row.get("kind") != "disruption":
            continue
        docs.append(
            Document(
                doc_id=f"dataset-disruption-{idx}",
                text=" ".join([str(row.get("description", "")), str(row.get("region", "")), str(row.get("disruption_type", ""))]),
                metadata={"kind": "dataset_history", "category": row.get("disruption_type", "other").replace(" ", "_").lower(), **row},
            )
        )
    return docs


def runtime_documents() -> list[Document]:
    if not init_db():
        return []
    try:
        with connect() as conn:
            token = "?" if getattr(conn, "agentic_scd_dialect", None) == "sqlite" else "%s"
            signal_rows = execute(
                conn,
                f"SELECT signal_id, title, raw_text, source_type, location, raw_payload FROM signals ORDER BY created_at DESC LIMIT {token}",
                (50,),
            ).fetchall()
    except Exception:
        return []
    docs: list[Document] = []
    for row in signal_rows:
        location = parse_json(row_value(row, "location", 4))
        payload = parse_json(row_value(row, "raw_payload", 5))
        region = location.get("region") or payload.get("region") or ""
        category = (
            payload.get("label")
            or payload.get("kind")
            or payload.get("disruption_type")
            or payload.get("webhook_event", {}).get("payload", {}).get("label")
            or "runtime_signal"
        )
        text = " ".join(
            [
                str(row_value(row, "title", 1)),
                str(row_value(row, "raw_text", 2)),
                str(row_value(row, "source_type", 3)),
                str(region),
                str(category),
            ]
        )
        docs.append(
            Document(
                doc_id=str(row_value(row, "signal_id", 0)),
                text=text,
                metadata={
                    "kind": "runtime_signal",
                    "category": str(category).replace(" ", "_").lower(),
                    "region": region,
                    "source_type": row_value(row, "source_type", 3),
                },
            )
        )
    return docs


def impact_documents() -> list[Document]:
    return network_documents() + synthetic_history_documents() + kaggle_history_documents() + runtime_documents()


def mitigation_documents() -> list[Document]:
    return playbook_documents() + runtime_documents()


@lru_cache(maxsize=1)
def impact_retriever() -> LocalRetriever:
    return LocalRetriever(impact_documents)


@lru_cache(maxsize=1)
def mitigation_retriever() -> LocalRetriever:
    return LocalRetriever(mitigation_documents)
