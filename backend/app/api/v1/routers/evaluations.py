from fastapi import APIRouter

from app.api.v1.schemas.models import EvaluationData, EvaluationRun, EvaluationRunRequest, EvaluationSettings
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/evaluations", response_model=EvaluationData)
def get_evaluations() -> EvaluationData:
    return store.evaluation_state


@router.post("/evaluations/run")
def run_evaluation(payload: EvaluationRunRequest) -> dict:
    run = EvaluationRun(
        id=store._id("ev"),
        label=payload.dataset,
        date="Just now",
        score=store.evaluation_state.meta.threshold,
        status="running",
        questions=payload.sampleSize,
    )
    store.evaluation_state.runs.insert(0, run)
    store.evaluation_state.meta.pipeline = payload.pipeline
    store.evaluation_state.meta.dataset = payload.dataset
    store.evaluation_state.meta.total = payload.sampleSize
    store.evaluation_state.meta.lastEvaluated = "just now"
    return {"id": run.id, "status": run.status, "startedAt": store._now_iso()}


@router.patch("/evaluations/settings", response_model=EvaluationSettings)
def update_evaluation_settings(payload: dict) -> EvaluationSettings:
    data = store.evaluation_state.settings.model_dump()
    data.update(payload or {})
    store.evaluation_state.settings = EvaluationSettings(**data)
    return store.evaluation_state.settings
