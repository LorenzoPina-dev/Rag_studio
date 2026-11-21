from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response

from app.api.v1.schemas.models import (
    Execution,
    Pipeline,
    PipelineCreate,
    PipelineRunRequest,
    PipelineSummary,
    PipelineUpdate,
    ValidationResult,
)
from app.application.codegen import generate_python_script
from app.application.execution_service import create_pipeline_execution
from app.application.pipeline_persistence import (
    create_pipeline as create_pipeline_record,
    delete_pipeline as delete_pipeline_record,
    duplicate_pipeline as duplicate_pipeline_record,
    get_pipeline as get_pipeline_record,
    list_pipeline_summaries,
    save_pipeline as save_pipeline_record,
)
from app.application.validation_service import validate_pipeline_api

router = APIRouter()


@router.get("/pipelines", response_model=list[PipelineSummary])
async def list_pipelines() -> list[PipelineSummary]:
    return await list_pipeline_summaries()


@router.get("/pipelines/{pipeline_id}", response_model=Pipeline)
async def get_pipeline(pipeline_id: str) -> Pipeline:
    pipeline = await get_pipeline_record(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/pipelines/{pipeline_id}/export")
async def export_pipeline(
    pipeline_id: str,
    format: Literal["json", "python"] = "json",
    query: str | None = None,
) -> Any:
    pipeline = await get_pipeline_record(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if format == "python":
        script = generate_python_script(pipeline, query=query)
        safe_name = pipeline.name.lower().replace(" ", "-")
        return Response(
            content=script,
            media_type="text/x-python",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.py"'},
        )
    return pipeline


@router.post("/pipelines", response_model=Pipeline)
async def create_pipeline(payload: PipelineCreate) -> Pipeline:
    return await create_pipeline_record(payload)


@router.patch("/pipelines/{pipeline_id}", response_model=Pipeline)
async def update_pipeline(pipeline_id: str, payload: PipelineUpdate) -> Pipeline:
    existing = await get_pipeline_record(pipeline_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    data = existing.model_dump()
    updates = payload.model_dump(exclude_unset=True)
    data.update(updates)
    updated = Pipeline(**data)
    return await save_pipeline_record(updated)


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str) -> dict[str, bool]:
    if not await delete_pipeline_record(pipeline_id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"ok": True}


@router.post("/pipelines/{pipeline_id}/validate", response_model=ValidationResult)
async def validate_pipeline(pipeline_id: str) -> ValidationResult:
    pipeline = await get_pipeline_record(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return validate_pipeline_api(pipeline)


@router.post("/pipelines/{pipeline_id}/run", response_model=Execution)
async def run_pipeline(pipeline_id: str, payload: PipelineRunRequest | None = None) -> Execution:
    pipeline = await get_pipeline_record(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    runtime_inputs: dict[str, dict[str, Any]] = {}
    if payload is not None:
        if payload.inputs:
            runtime_inputs.update({node_id: dict(values) for node_id, values in payload.inputs.items()})
        if payload.query:
            for node in pipeline.nodes:
                if node.kind in {"input", "query-input"}:
                    runtime_inputs.setdefault(node.id, {})["query"] = payload.query

    execution = await create_pipeline_execution(pipeline, runtime_inputs=runtime_inputs or None)
    pipeline.lastRun = None
    return execution


@router.post("/pipelines/{pipeline_id}/duplicate", response_model=Pipeline)
async def duplicate_pipeline(pipeline_id: str) -> Pipeline:
    duplicate = await duplicate_pipeline_record(pipeline_id)
    if duplicate is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return duplicate
