"""Document loading shared by dataset imports, runtime, comparison and export.

Datasets stay editable JSON files; filters applied here are plain stdlib so the
same selection can be reused by nodes, comparison and exported scripts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.components.algorithms import DEFAULT_CORPUS, filter_documents
from app.core.config import settings

REQUIRED_FIELDS = ("id", "title", "source", "content")
OPTIONAL_FIELDS = ("fileType",)

__all__ = [
    "filter_documents",
    "load_documents",
    "load_documents_for_dataset",
    "normalize_documents",
    "dataset_id_from_pipeline",
]


def normalize_documents(raw: Any, origin: str = "dataset") -> list[dict[str, str]]:
    """Validate and normalize a list of documents coming from any connector."""
    if not isinstance(raw, list):
        raise ValueError(f"{origin}: expected a JSON list of documents")
    documents: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{origin}: document #{index} must be an object")
        missing = [field for field in REQUIRED_FIELDS if not str(item.get(field, "")).strip()]
        if missing:
            raise ValueError(f"{origin}: document #{index} is missing: {', '.join(missing)}")
        document = {field: str(item[field]) for field in REQUIRED_FIELDS}
        for field in OPTIONAL_FIELDS:
            if item.get(field) not in (None, ""):
                document[field] = str(item[field])
        documents.append(document)
    return documents


def load_documents(path: str | Path | None = None) -> list[dict[str, str]]:
    """Return the documents from ``path`` (or the configured default dataset).

    A missing file falls back to the built-in demo corpus so the app still
    starts. A malformed file raises a readable error instead of being ignored.
    """
    dataset_path = Path(path) if path is not None else Path(settings.rag_dataset_path)
    if not dataset_path.exists():
        return [dict(item) for item in DEFAULT_CORPUS]

    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in RAG dataset {dataset_path}: {exc}") from exc

    return normalize_documents(raw, str(dataset_path))


def load_documents_for_dataset(
    identifier: str | None = None,
    file_types: str | Iterable[str] | None = None,
    file_name: str | None = None,
) -> list[dict[str, str]]:
    """Load and filter the documents of a project dataset (by id or name).

    No identifier means the default `documents.json` corpus. Unknown
    identifiers raise a clear error so a wrong node setting is visible.
    """
    if not identifier:
        documents = load_documents()
    else:
        from app.components.dataset_connectors import fetch_documents
        from app.infrastructure.dataset_store import get_dataset

        dataset = get_dataset(str(identifier))
        if dataset.items:
            # Inline documents (legacy datasets or import API): use what is stored.
            documents = [item.model_dump() for item in dataset.items]
        elif dataset.path:
            # Connector-backed dataset: extract text here, at pipeline time. Sync
            # only scans metadata, so the JSON never holds megabytes of PDF text.
            documents = fetch_documents(dataset.sourceType, dataset.path, dataset.connection)
        else:
            documents = []
    return filter_documents(documents, file_types, file_name)


def dataset_id_from_pipeline(pipeline: Any) -> str | None:
    """Read the dataset selected in the first Document source node of a graph."""
    if not isinstance(pipeline, dict):
        pipeline = pipeline.model_dump() if hasattr(pipeline, "model_dump") else {}
    for node in pipeline.get("nodes") or []:
        node_data = node if isinstance(node, dict) else {}
        definition = str(node_data.get("definitionId") or "")
        kind = str(node_data.get("kind") or "")
        if definition == "document-source" or kind in {"source", "data-source"}:
            config = node_data.get("config") or {}
            if isinstance(config, dict):
                selected = config.get("dataset") or config.get("datasetId")
                if selected:
                    return str(selected)
    return None
