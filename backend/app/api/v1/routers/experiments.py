from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.models import Experiment, ExperimentComparison, ExperimentCreateRequest, ExperimentData
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/experiments", response_model=ExperimentData)
def get_experiments() -> ExperimentData:
    return store.experiment_data()


@router.post("/experiments", response_model=Experiment)
def create_experiment(payload: ExperimentCreateRequest) -> Experiment:
    exp = Experiment(
        id=store._id("exp"),
        name=payload.name,
        chunking="Semantic · 512",
        retrieval="Hybrid α0.7",
        selection="Top-K · 5",
        faithfulness=None,
        latency=None,
        cost=None,
        status="draft",
        tags=["new"],
        project="Knowledge assistant",
        createdAt="Just now",
    )
    store.experiments.insert(0, exp)
    return exp


@router.post("/experiments/compare", response_model=ExperimentComparison)
def compare_experiments(payload: dict) -> ExperimentComparison:
    ids = (payload or {}).get("ids") or store.experiment_data().comparison.ids
    selected = [e for e in store.experiments if e.id in ids]
    if not selected:
        selected = store.experiments[:3]
    scatter = [
        {
            "id": e.id,
            "name": e.name,
            "latency": e.latency or 1.0,
            "faithfulness": e.faithfulness or 0.85,
            "accent": "#7296FF",
        }
        for e in selected
    ]
    params = [
        {"key": "Chunking", "values": [e.chunking for e in selected]},
        {"key": "Retrieval", "values": [e.retrieval for e in selected]},
        {"key": "Selection", "values": [e.selection for e in selected]},
    ]
    return ExperimentComparison(ids=[e.id for e in selected], parameters=params, scatter=scatter, insight="Comparison generated from selected experiments.")


@router.post("/experiments/{experiment_id}/promote")
def promote_experiment(experiment_id: str) -> dict:
    for e in store.experiments:
        if e.id == experiment_id:
            return {"ok": True, "experimentId": experiment_id}
    raise HTTPException(status_code=404, detail="Experiment not found")
