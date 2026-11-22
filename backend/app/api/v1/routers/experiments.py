"""Confronto e promozione di esperimenti usando risultati di esecuzione reali."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.models import Experiment, ExperimentComparison, ExperimentCreateRequest, ExperimentData
from app.components import advanced_algorithms as advanced
from app.infrastructure.memory import store

router = APIRouter()

_ACCENTS = ("#7296FF", "#A78BFA", "#35D99B", "#F0B45C", "#E48EF0")


def _has_real_output(result: Any) -> bool:
    return bool(result is not None and str(result.generatedAnswer or "").strip() and result.documents)


def _execution_ids(payload: dict[str, Any], experiment: Experiment) -> list[str]:
    mapping = payload.get("executionIds") or payload.get("execution_ids") or {}
    candidates = [
        mapping.get(experiment.id) if isinstance(mapping, dict) else None,
        experiment.executionId,
        experiment.id,
    ]
    return [str(item) for item in candidates if item]


def _load_result(payload: dict[str, Any], experiment: Experiment) -> tuple[str, Any]:
    for execution_id in _execution_ids(payload, experiment):
        result = store.get_execution_result(execution_id)
        if _has_real_output(result):
            return execution_id, result
    raise HTTPException(
        status_code=409,
        detail=(
            f"Risultati di esecuzione reali mancanti per l'esperimento '{experiment.id}': "
            "collegare un executionId con risultati salvati prima di confrontare."
        ),
    )


def _metrics(execution_id: str, result: Any) -> tuple[dict[str, float], str | None]:
    documents = [document.model_dump() for document in result.documents]
    answer = advanced.evaluate_answer(
        str(result.generatedAnswer), str(result.query), documents
    )
    execution = store.get_execution(execution_id) or store.get_execution(str(result.executionId))
    latency_ms = float(getattr(result.runtime, "latencyMs", 0) or 0)
    cost_value = float(getattr(execution, "cost", 0) or 0) if execution is not None else 0.0
    note = None
    if cost_value <= 0:
        note = f"Costo non disponibile per '{execution_id}': riportato come 0 senza stime."
    return {
        "faithfulness": float(answer.get("faithfulness") or 0.0),
        "relevance": float(answer.get("answer_relevance") or 0.0),
        "latency": max(0.0, latency_ms) / 1000.0,
        "cost": cost_value,
    }, note


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
        executionId=payload.executionId,
    )
    store.experiments.insert(0, exp)
    return exp


@router.post("/experiments/compare", response_model=ExperimentComparison)
def compare_experiments(payload: dict | None = None) -> ExperimentComparison:
    """Confronta metriche calcolate dagli ExecutionResult delle varianti."""
    request = payload or {}
    raw_ids = request.get("ids") or store.experiment_data().comparison.ids
    if isinstance(raw_ids, str):
        raw_ids = [raw_ids]
    ids = [str(item) for item in raw_ids]
    if not ids:
        raise HTTPException(status_code=409, detail="Nessun esperimento selezionato per il confronto.")

    selected: list[Experiment] = []
    for experiment_id in ids:
        experiment = next((e for e in store.experiments if e.id == experiment_id), None)
        if experiment is None:
            raise HTTPException(status_code=404, detail=f"Esperimento non trovato: {experiment_id}")
        selected.append(experiment)

    values: list[dict[str, float]] = []
    resolved_ids: list[str] = []
    notes: list[str] = []
    for experiment in selected:
        execution_id, result = _load_result(request, experiment)
        metrics, note = _metrics(execution_id, result)
        resolved_ids.append(execution_id)
        values.append(metrics)
        if note is not None:
            notes.append(note)
        experiment.faithfulness = metrics["faithfulness"]
        experiment.latency = metrics["latency"]
        experiment.cost = metrics["cost"]

    baseline = values[0]
    scatter: list[dict[str, Any]] = []
    for experiment, metrics in zip(selected, values):
        scatter.append(
            {
                "id": experiment.id,
                "name": experiment.name,
                "latency": metrics["latency"],
                "faithfulness": metrics["faithfulness"],
                "cost": metrics["cost"],
                "deltaLatency": round(metrics["latency"] - baseline["latency"], 6),
                "deltaFaithfulness": round(metrics["faithfulness"] - baseline["faithfulness"], 6),
                "deltaCost": round(metrics["cost"] - baseline["cost"], 6),
                "executionId": next(
                    (eid for eid, item in zip(resolved_ids, selected) if item.id == experiment.id),
                    None,
                ),
                "accent": _ACCENTS[len(scatter) % len(_ACCENTS)],
            }
        )

    parameters = [
        {"key": "Chunking", "values": [e.chunking for e in selected]},
        {"key": "Retrieval", "values": [e.retrieval for e in selected]},
        {"key": "Selection", "values": [e.selection for e in selected]},
    ]
    if len(scatter) > 1:
        parts = [
            f"{item['name']} vs {scatter[0]['name']}: "
            f"faithfulness {item['deltaFaithfulness']:+.4f}, "
            f"latenza {item['deltaLatency']:+.3f}s, "
            f"costo {item['deltaCost']:+.6f}"
            for item in scatter[1:]
        ]
        insight = "Confronto da risultati reali di esecuzione — " + "; ".join(parts) + "."
    else:
        insight = (
            "Confronto da risultati reali di esecuzione su un solo esperimento: "
            "nessun delta calcolabile senza un baseline."
        )
    if notes:
        insight += " " + " ".join(notes)

    return ExperimentComparison(
        ids=[e.id for e in selected],
        parameters=parameters,
        scatter=scatter,
        insight=insight,
    )


def _promote_linked_pipeline(experiment: Experiment, payload: dict[str, Any]) -> dict[str, Any] | None:
    execution_id = payload.get("executionId") or experiment.executionId
    execution = store.get_execution(str(execution_id)) if execution_id else None
    pipeline_id = payload.get("pipelineId") or (execution.pipelineId if execution else None)
    if not pipeline_id:
        return None
    pipeline = store.get_pipeline(str(pipeline_id))
    if pipeline is None:
        return None
    if pipeline.id in store.created_pipelines or pipeline is store.active_pipeline:
        pipeline.status = "valid"
        pipeline.updatedAt = store._now_iso()
        store.save_pipeline(pipeline)
    return {"pipelineId": pipeline.id, "status": pipeline.status}


@router.post("/experiments/{experiment_id}/promote")
def promote_experiment(experiment_id: str, payload: dict | None = None) -> dict[str, Any]:
    """Promuove davvero l'esperimento nello store e, se collegata, la pipeline."""
    request = payload or {}
    for index, experiment in enumerate(store.experiments):
        if experiment.id != experiment_id:
            continue
        promoted_at = store._now_iso()
        experiment.promoted = True
        experiment.promotedAt = promoted_at
        if experiment.status in {"draft", "running", "failed"}:
            experiment.status = "complete"
        store.experiments[index] = experiment
        pipeline = _promote_linked_pipeline(experiment, request)
        detail = (
            "Esperimento promosso e pipeline collegata aggiornata."
            if pipeline is not None
            else "Esperimento promosso; nessuna pipeline collegata da aggiornare."
        )
        return {
            "ok": True,
            "experimentId": experiment_id,
            "status": experiment.status,
            "promoted": experiment.promoted,
            "promotedAt": promoted_at,
            "pipeline": pipeline,
            "detail": detail,
        }
    raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}")
