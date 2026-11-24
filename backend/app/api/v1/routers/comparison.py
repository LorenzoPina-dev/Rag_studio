"""Real side-by-side comparison of RAG algorithm configurations."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.pipeline_persistence import get_pipeline as get_pipeline_record
from app.components.algorithms import PIPELINE_DEFAULTS, config_from_pipeline, run_pipeline
from app.components.corpus import dataset_id_from_pipeline, load_documents_for_dataset
from app.providers import hooks as provider_hooks
from app.providers.resolver import ProviderUnavailableError

router = APIRouter()


class ComparisonVariant(BaseModel):
    id: str
    label: str
    pipelineId: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ComparisonRequest(BaseModel):
    query: str
    variants: list[ComparisonVariant]
    datasetId: str | None = None


class VariantResult(BaseModel):
    id: str
    label: str
    config: dict[str, Any]
    answer: str
    citations: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    metrics: dict[str, Any]
    durationMs: float


class ComparisonResponse(BaseModel):
    query: str
    variants: list[VariantResult]


@router.post("/comparison/run", response_model=ComparisonResponse)
async def compare_variants(payload: ComparisonRequest) -> ComparisonResponse:
    results: list[VariantResult] = []
    documents_by_dataset: dict[str | None, list[dict[str, Any]]] = {}

    for variant in payload.variants:
        pipeline: Any = None
        if variant.pipelineId:
            pipeline = await get_pipeline_record(variant.pipelineId)
            if pipeline is None:
                raise HTTPException(status_code=404, detail=f"Pipeline not found: {variant.pipelineId}")
            config = config_from_pipeline(pipeline)
        else:
            config = dict(PIPELINE_DEFAULTS)
        config.update(variant.config)

        # Explicit variant/request dataset wins; otherwise use the dataset
        # selected by the variant's document-source node.
        declared_dataset = variant.config.get("datasetId") or variant.config.get("dataset")
        dataset_id = declared_dataset or payload.datasetId
        if not dataset_id and pipeline is not None:
            dataset_id = dataset_id_from_pipeline(pipeline)
        dataset_key = str(dataset_id) if dataset_id else None
        if dataset_key not in documents_by_dataset:
            try:
                documents_by_dataset[dataset_key] = await asyncio.to_thread(
                    load_documents_for_dataset, dataset_id
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        source_documents = documents_by_dataset[dataset_key]

        try:
            hooks = await asyncio.to_thread(provider_hooks.build_provider_hooks, config)
            started = time.perf_counter()
            result = await asyncio.to_thread(
                run_pipeline,
                payload.query,
                config,
                source_documents,
                provider_hooks=hooks,
            )
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
        except (ProviderUnavailableError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        variant_documents = [
            {
                "rank": item.get("rank"),
                "title": item.get("title"),
                "source": item.get("source"),
                "chunkId": item.get("chunk_id"),
                "score": item.get("score"),
                "excerpt": item.get("content", "")[:180],
            }
            for item in result["selected"]
        ]
        results.append(
            VariantResult(
                id=variant.id,
                label=variant.label,
                config=result["config"],
                answer=result["answer"]["text"],
                citations=result["answer"]["citations"],
                documents=variant_documents,
                metrics=result["metrics"],
                durationMs=duration_ms,
            )
        )
    return ComparisonResponse(query=payload.query, variants=results)
