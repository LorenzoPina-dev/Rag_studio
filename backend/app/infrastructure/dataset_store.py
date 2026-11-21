"""Project datasets: editable, file-backed and shared by every RAG path.

Datasets are the single source of truth for documents. The JSON file lives next
to the default corpus (`backend/data/`) and is rewritten on each mutation, so
the UI can create/import/sync datasets without a database.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.api.v1.schemas.models import Dataset, DatasetDocument, DatasetFile, DataSource
from app.components.corpus import load_documents, normalize_documents
from app.components.dataset_connectors import (
    CONNECTORS,
    documents_from_text,
    files_from_documents,
    scan_files,
)
from app.core.config import settings
from app.infrastructure.memory import store

DATA_PATH = Path(settings.rag_dataset_path).parent / "datasets.json"
_lock = threading.RLock()
_datasets: list[Dataset] | None = None


def _recount(dataset: Dataset, count: int | None = None) -> None:
    total = len(dataset.items) if count is None else count
    dataset.documents = total
    dataset.chunks = 0  # chunking happens in the pipeline, never during sync
    dataset.documentsProcessed = total
    dataset.documentsTotal = total
    dataset.lastSync = "Just now"
    dataset.status = "indexed" if total else "ingesting"
    dataset.health = "healthy"


def _save() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DATA_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps([dataset.model_dump() for dataset in _datasets or []], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(DATA_PATH)


def _seed() -> list[Dataset]:
    datasets = [dataset.model_copy(deep=True) for dataset in store.datasets]
    if datasets:
        documents = load_documents()
        datasets[0].items = [DatasetDocument(**document) for document in documents]
        datasets[0].files = [DatasetFile(**item) for item in files_from_documents(documents)]
        _recount(datasets[0])
    return datasets


def ensure_loaded() -> list[Dataset]:
    global _datasets
    with _lock:
        if _datasets is None:
            if DATA_PATH.exists():
                raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError(f"Dataset file {DATA_PATH} must contain a JSON list")
                _datasets = [Dataset(**item) for item in raw]
            else:
                _datasets = _seed()
                _save()
            store.datasets = _datasets
        return _datasets


def list_datasets() -> list[Dataset]:
    return ensure_loaded()


def dataset_options() -> list[dict[str, str]]:
    return [
        {"value": dataset.id, "label": dataset.name, "description": dataset.sourceType}
        for dataset in ensure_loaded()
    ]


def get_dataset(identifier: str) -> Dataset:
    for dataset in ensure_loaded():
        if dataset.id == identifier or dataset.name.lower() == identifier.lower():
            return dataset
    raise ValueError(f"Dataset non trovato: {identifier}")


def create_dataset(payload: dict[str, Any]) -> Dataset:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Il dataset deve avere un nome")
    source_type = str(payload.get("sourceType") or "Local files")
    if source_type not in CONNECTORS:
        raise ValueError(f"Connettore non supportato: {source_type}")

    with _lock:
        datasets = ensure_loaded()
        if any(dataset.name.lower() == name.lower() for dataset in datasets):
            raise ValueError(f"Esiste già un dataset chiamato {name}")

        items = normalize_documents(payload.get("items") or [], name)
        dataset = Dataset(
            id=store._id("ds"),
            name=name,
            sourceType=source_type,
            format=str(payload.get("format") or "Text · JSON"),
            documents=0,
            chunks=0,
            lastSync="Just now",
            status="indexed" if items else "ingesting",
            path=str(payload.get("path") or ""),
            embedding=str(payload.get("embedding") or "bge-large-en-v1.5"),
            chunking=str(payload.get("chunking") or "Semantic · 512 tokens"),
            usedBy=0,
            size="—",
            health="healthy",
            items=[DatasetDocument(**item) for item in items],
            files=[DatasetFile(**item) for item in files_from_documents(items)],
            connection=dict(payload.get("connection") or {}),
        )
        _recount(dataset)
        datasets.insert(0, dataset)
        store.data_sources.insert(
            0,
            DataSource(
                id=store._id("src"),
                name=name,
                type=source_type,  # type: ignore[arg-type]
                status="connected",
                documents=len(items),
                lastSync="Just now",
                config=dataset.path or name,
                datasets=1,
            ),
        )
        _save()
        return dataset


def update_dataset(dataset_id: str, payload: dict[str, Any]) -> Dataset:
    with _lock:
        dataset = get_dataset(dataset_id)
        data = dataset.model_dump()
        data.update(payload or {})
        data.pop("id", None)
        updated = Dataset(**data)
        if "items" in (payload or {}):
            updated.items = [DatasetDocument(**item) for item in normalize_documents(payload["items"], updated.name)]
            _recount(updated)
        for index, current in enumerate(ensure_loaded()):
            if current.id == dataset.id:
                ensure_loaded()[index] = updated
                break
        _save()
        return updated


def add_documents(dataset_id: str, filename: str, text: str) -> Dataset:
    documents = documents_from_text(filename, text)
    with _lock:
        dataset = get_dataset(dataset_id)
        dataset.items.extend(DatasetDocument(**document) for document in documents)
        known = {file.id for file in dataset.files}
        dataset.files.extend(
            DatasetFile(**item) for item in files_from_documents(documents) if item["id"] not in known
        )
        _recount(dataset)
        _save()
        return dataset


def sync_dataset(dataset_id: str) -> Dataset:
    """Refresh only the file inventory: text extraction belongs to the pipeline."""
    with _lock:
        dataset = get_dataset(dataset_id)
        inventory = scan_files(dataset.sourceType, dataset.path, dataset.connection)
        dataset.files = [DatasetFile(**item) for item in inventory]
        if dataset.path:
            # Connector-backed datasets never cache extracted text in datasets.json.
            dataset.items = []
            _recount(dataset, count=sum(1 for file in inventory if file["indexed"]))
        else:
            # Legacy inline datasets (no path) keep their stored documents.
            _recount(dataset)
        _save()
        return dataset


def delete_dataset(dataset_id: str) -> None:
    with _lock:
        dataset = get_dataset(dataset_id)
        datasets = ensure_loaded()
        datasets.remove(dataset)
        store.data_sources[:] = [source for source in store.data_sources if source.name != dataset.name]
        _save()
