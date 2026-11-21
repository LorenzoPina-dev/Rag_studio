from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.schemas.models import Dataset, DatasetDocument, DatasetMetrics, DatasetsData, IngestionJob
from app.components.dataset_connectors import CONNECTORS
from app.infrastructure import dataset_store
from app.infrastructure.memory import store

router = APIRouter()


class DatasetCreate(BaseModel):
    name: str
    sourceType: str = "Local files"
    path: str = ""
    format: str = "Text · JSON"
    items: list[dict[str, Any]] = Field(default_factory=list)
    connection: dict[str, Any] = Field(default_factory=dict)


class DocumentImport(BaseModel):
    filename: str = "pasted.txt"
    text: str = ""


@router.get("/datasets", response_model=DatasetsData)
def list_datasets() -> DatasetsData:
    """Return dataset metadata and file inventory, with short content previews.

    Full document text can be megabytes for PDF datasets: the list keeps only
    an excerpt, while ``GET /datasets/:id`` still returns the full documents.
    """
    dataset_store.ensure_loaded()
    data = store.datasets_data()
    summaries = []
    for dataset in data.datasets:
        summary = dataset.model_copy(deep=True)
        summary.items = [
            item.model_copy(update={"content": item.content[:240]}) for item in summary.items
        ]
        summaries.append(summary)
    data.datasets = summaries
    return data


@router.get("/datasets/metrics", response_model=DatasetMetrics)
def dataset_metrics() -> DatasetMetrics:
    dataset_store.ensure_loaded()
    return store.datasets_data().metrics


@router.get("/datasets/connectors")
def list_connectors() -> dict[str, list[str]]:
    return {"connectors": CONNECTORS}


@router.get("/datasets/options")
def dataset_select_options() -> list[dict[str, str]]:
    return dataset_store.dataset_options()


@router.post("/datasets", response_model=Dataset, status_code=201)
def create_dataset(payload: DatasetCreate) -> Dataset:
    try:
        return dataset_store.create_dataset(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/datasets/sync")
def sync_all_datasets() -> dict:
    return {"ok": True, "syncedAt": store._now_iso()}


@router.get("/datasets/{dataset_id}", response_model=Dataset)
def get_dataset(dataset_id: str) -> Dataset:
    try:
        return dataset_store.get_dataset(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/datasets/{dataset_id}", response_model=Dataset)
def update_dataset(dataset_id: str, payload: dict) -> Dataset:
    try:
        return dataset_store.update_dataset(dataset_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str) -> None:
    try:
        dataset_store.delete_dataset(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/documents", response_model=Dataset)
def import_documents(dataset_id: str, payload: DocumentImport) -> Dataset:
    try:
        return dataset_store.add_documents(dataset_id, payload.filename, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/sync", response_model=Dataset)
def sync_dataset(dataset_id: str) -> Dataset:
    try:
        return dataset_store.sync_dataset(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/reindex")
def reindex_dataset(dataset_id: str) -> dict:
    try:
        dataset = dataset_store.get_dataset(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = IngestionJob(
        id=store._id("job"),
        datasetName=dataset.name,
        status="running",
        progress=0,
        startedAt="Just now",
        duration="0s",
        documents=dataset.documents,
        errors=0,
    )
    store.ingestion_jobs.insert(0, job)
    return {"ok": True, "datasetId": dataset.id, "jobId": job.id}


@router.get("/ingestion-jobs", response_model=list[IngestionJob])
def list_ingestion_jobs() -> list[IngestionJob]:
    return store.ingestion_jobs
