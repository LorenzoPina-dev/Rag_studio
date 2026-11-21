"""Real side-by-side comparison of RAG algorithm configurations."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.pipeline_persistence import get_pipeline as get_pipeline_record
from app.components.algorithms import PIPELINE_DEFAULTS, config_from_pipeline, run_pipeline
from app.components.corpus import load_documents_for_dataset

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
    try:
        documents = load_documents_for_dataset(payload.datasetId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    results: list[VariantResult] = []
    for variant in payload.variants:
        config = dict(PIPELINE_DEFAULTS)
        if variant.pipelineId:
            pipeline = await get_pipeline_record(variant.pipelineId)
            if pipeline is None:
                raise HTTPException(status_code=404, detail=f"Pipeline not found: {variant.pipelineId}")
            config = config_from_pipeline(pipeline)
        config.update(variant.config)

        started = time.perf_counter()
        result = run_pipeline(payload.query, config, documents)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        documents = [
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
                documents=documents,
                metrics=result["metrics"],
                durationMs=duration_ms,
            )
        )
    return ComparisonResponse(query=payload.query, variants=results)
