from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.v1.schemas.models import Execution, ExecutionResult, LogEntry, NodeExecutionRecord
from app.application.execution_runtime import (
    append_api_log,
    emit_domain_event,
    sync_domain_execution_projection,
    transition_api_execution,
)
from app.application.execution_persistence import (
    list_execution_artifacts,
    load_execution_artifact,
    load_execution_result,
)
from app.application.execution_service import create_pipeline_execution
from app.application.execution_store import get_api_execution, list_api_executions
from app.application.execution_stream import stream_execution_events
from app.application.node_execution_persistence import list_node_executions
from app.core.bootstrap import container
from app.domain.contracts.execution import ExecutionEventType
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/executions", response_model=list[Execution])
async def list_executions() -> list[Execution]:
    return await list_api_executions()


@router.get("/executions/{execution_id}", response_model=Execution)
async def get_execution(execution_id: str) -> Execution:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.post("/executions", response_model=Execution)
async def start_execution() -> Execution:
    # ad-hoc start: run active pipeline
    pipeline = store.active_pipeline
    return await create_pipeline_execution(pipeline, trigger="Triggered manually (ad-hoc)")


@router.post("/executions/{execution_id}/stop")
async def stop_execution(execution_id: str) -> dict:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    previous = execution.status
    if previous not in {"completed", "failed", "stopped"}:
        transition_api_execution(execution, "stopped", force=True)
        append_api_log(execution, "WARN", "Execution stopped by user")
        await emit_domain_event(
            execution.id,
            ExecutionEventType.EXECUTION_CANCELLED,
            status="stopped",
            level="warn",
            message="Execution stopped by user",
            payload={"previousStatus": previous},
        )
        await sync_domain_execution_projection(execution)

    return {"ok": True, "status": execution.status}


@router.get("/executions/{execution_id}/logs", response_model=list[LogEntry])
async def get_execution_logs(execution_id: str) -> list[LogEntry]:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution.logs


@router.get("/executions/{execution_id}/nodes", response_model=list[NodeExecutionRecord])
async def get_execution_nodes(execution_id: str) -> list[NodeExecutionRecord]:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return await list_node_executions(execution_id)


@router.get("/executions/{execution_id}/events")
async def get_execution_events(execution_id: str) -> list[dict]:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    repo = getattr(container, "execution_repository", None)
    events = []
    if repo is not None and hasattr(repo, "list_events"):
        events = await repo.list_events(execution_id)
    else:
        publisher = getattr(container, "event_publisher", None)
        if publisher is not None and hasattr(publisher, "list"):
            events = publisher.list(execution_id)

    out: list[dict] = []
    for e in events:
        if hasattr(e, "model_dump"):
            data = e.model_dump()
        elif hasattr(e, "dict"):
            data = e.dict()  # type: ignore[attr-defined]
        else:
            data = dict(getattr(e, "__dict__", {}))
        t = data.get("type")
        if hasattr(t, "value"):
            data["type"] = t.value
        ts = data.get("timestamp")
        if hasattr(ts, "isoformat"):
            data["timestamp"] = ts.isoformat()
        out.append(data)
    return out


@router.get("/executions/{execution_id}/results", response_model=ExecutionResult)
async def get_execution_results(execution_id: str) -> ExecutionResult:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    result = await load_execution_result(execution_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Execution results are not available yet")
    return result


async def _artifact_payload(execution_id: str, ref) -> dict:
    artifact_store = getattr(container, "artifact_store", None)
    url: str | None = None
    if artifact_store is not None and getattr(ref, "storage", None) != "memory":
        try:
            candidate = await artifact_store.get_url(ref)
            # Only browser-fetchable URLs are exposed; filesystem/file:// refs
            # use the API proxy path below.
            if candidate and candidate.startswith(("http://", "https://")):
                url = candidate
        except Exception:
            url = None
    metadata = dict(getattr(ref, "metadata", None) or {})
    return {
        "id": getattr(ref, "artifact_id", None),
        "name": metadata.get("name"),
        "kind": metadata.get("kind"),
        "contentType": getattr(ref, "content_type", None),
        "sizeBytes": getattr(ref, "size_bytes", None),
        "url": url or f"/api/v1/executions/{execution_id}/artifacts/{ref.artifact_id}/content",
    }


@router.get("/executions/{execution_id}/artifacts")
async def get_execution_artifacts(execution_id: str) -> list[dict]:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    refs = await list_execution_artifacts(execution_id)
    return [await _artifact_payload(execution_id, ref) for ref in refs]


@router.get("/executions/{execution_id}/artifacts/{artifact_id}")
async def get_execution_artifact(execution_id: str, artifact_id: str) -> dict:
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    ref = await load_execution_artifact(execution_id, artifact_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Artifact not found for this execution")
    return await _artifact_payload(execution_id, ref)


@router.get("/executions/{execution_id}/artifacts/{artifact_id}/content")
async def get_execution_artifact_content(execution_id: str, artifact_id: str):
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    ref = await load_execution_artifact(execution_id, artifact_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Artifact not found for this execution")

    artifact_store = getattr(container, "artifact_store", None)
    if artifact_store is None:
        raise HTTPException(status_code=404, detail="Artifact store unavailable")
    try:
        if getattr(ref, "content_type", None) == "application/json":
            return JSONResponse(content=await artifact_store.get_json(ref))
        return Response(
            content=await artifact_store.get_bytes(ref),
            media_type=getattr(ref, "content_type", None) or "application/octet-stream",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"Artifact content unavailable: {exc}") from exc


@router.get("/executions/{execution_id}/stream")
async def stream_execution(execution_id: str):
    execution = await get_api_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    return StreamingResponse(
        stream_execution_events(execution),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
