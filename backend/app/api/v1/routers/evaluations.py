"""Valutazione su output reali di esecuzioni memorizzate."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.models import (
    EvaluationData,
    EvaluationRun,
    EvaluationRunRequest,
    EvaluationSettings,
    EvaluationSettingsUpdate,
    QuestionResult,
    TrendPoint,
)
from app.components import advanced_algorithms as advanced
from app.components import algorithms as alg
from app.infrastructure.memory import store

router = APIRouter()

_METRIC_KEYS = {
    "faithfulness": "faithfulness",
    "relevance": "relevance",
    "precision": "precision",
    "recall": "recall",
}


def _document_records(result: Any) -> list[dict[str, Any]]:
    return [document.model_dump() for document in result.documents]


def _has_real_output(result: Any) -> bool:
    return bool(result is not None and str(result.generatedAnswer or "").strip() and result.documents)


def _relevant_ids(payload: EvaluationRunRequest, execution_id: str) -> list[str]:
    if payload.relevantIds:
        return [str(item) for item in payload.relevantIds]
    artifacts = store.execution_artifacts.get(execution_id, {}) or {}
    raw = artifacts.get("relevantIds") or artifacts.get("relevant_ids") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item) for item in raw]


def _weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = 0.0
    weighted = 0.0
    for name, value in components.items():
        weight = float(weights.get(name, 0.0) or 0.0)
        total_weight += weight
        weighted += value * weight
    if total_weight <= 0:
        raise ValueError("I pesi delle metriche di valutazione sono tutti zero: impossibile calcolare lo score.")
    return weighted / total_weight


@router.get("/evaluations", response_model=EvaluationData)
def get_evaluations() -> EvaluationData:
    return store.evaluation_state


@router.post("/evaluations/run")
def run_evaluation(payload: EvaluationRunRequest) -> dict[str, Any]:
    """Calcola metriche reali dai documenti e dalla risposta di una esecuzione."""
    if payload.executionId:
        result = store.get_execution_result(payload.executionId)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Esecuzione '{payload.executionId}' non trovata o senza risultati salvati.",
            )
        execution_id = payload.executionId
    else:
        result = None
        execution_id = ""
        # L'ultima inserita è la più recente: lo store in memoria mantiene l'ordine.
        for candidate_id in reversed(list(store.execution_results)):
            candidate = store.get_execution_result(candidate_id)
            if _has_real_output(candidate):
                result = candidate
                execution_id = candidate_id
                break
        if result is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Nessuna esecuzione con risultati reali disponibili: "
                    "eseguire una pipeline o indicare executionId nel payload."
                ),
            )

    if not _has_real_output(result):
        raise HTTPException(
            status_code=409,
            detail=(
                f"L'esecuzione '{execution_id}' non contiene una risposta generata e documenti reali: "
                "impossibile calcolare metriche di valutazione."
            ),
        )

    documents = _document_records(result)
    retrieved = [str(document.get("chunkId") or document.get("id") or "") for document in documents]
    relevant = _relevant_ids(payload, execution_id)
    try:
        retrieval_metrics = alg.evaluate_retrieval(
            retrieved, relevant, k=max(1, len(retrieved))
        )
        answer_metrics = advanced.evaluate_answer(
            str(result.generatedAnswer),
            str(result.query),
            documents,
            relevant_ids=relevant,
        )
        weights = dict(store.evaluation_state.settings.metricWeights or {})
        components = {
            "faithfulness": float(answer_metrics.get("faithfulness") or 0.0),
            "relevance": float(answer_metrics.get("answer_relevance") or 0.0),
            "precision": float(retrieval_metrics.get("precision") or 0.0),
            "recall": float(retrieval_metrics.get("recall") or 0.0),
        }
        score = _weighted_score(components, weights)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=f"Impossibile calcolare le metriche: {exc}") from exc

    state = store.evaluation_state
    threshold = float(state.meta.threshold)
    passed = score >= threshold
    for metric in state.metrics:
        key = _METRIC_KEYS.get(metric.id)
        if key is not None:
            metric.value = components[key]

    previous_score = state.runs[0].score if state.runs else None
    for point in state.comparison:
        key = _METRIC_KEYS.get(str(point.metric or "").lower())
        if key is not None:
            point.current = components[key]
    if previous_score is not None:
        state.trend.append(
            TrendPoint(date=store._today_time(), current=score, baseline=float(previous_score))
        )

    state.questions.insert(
        0,
        QuestionResult(
            id=f"q_{execution_id}",
            question=str(result.query),
            faithfulness=components["faithfulness"],
            relevance=components["relevance"],
            contextPrecision=components["precision"],
            contextRecall=components["recall"],
            passed=passed,
            reviewStatus="passed" if passed else "review",
        ),
    )
    run = EvaluationRun(
        id=store._id("ev"),
        label=payload.dataset,
        date=store._today_time(),
        score=score,
        status="completed",
        questions=1,
    )
    state.runs.insert(0, run)
    state.meta.pipeline = payload.pipeline
    state.meta.dataset = payload.dataset
    state.meta.total = 1
    state.meta.passed = 1 if passed else 0
    state.meta.failed = 0 if passed else 1
    state.meta.lastEvaluated = store._now_iso()

    return {
        "id": run.id,
        "status": run.status,
        "startedAt": store._now_iso(),
        "executionId": execution_id,
        "score": score,
        "passed": passed,
        "metrics": components,
        "detail": (
            f"Metriche calcolate sull'output dell'esecuzione '{execution_id}'. "
            f"{len(relevant)} id rilevanti forniti per il retrieval."
        ),
    }


@router.patch("/evaluations/settings", response_model=EvaluationSettings)
def update_evaluation_settings(payload: EvaluationSettingsUpdate) -> EvaluationSettings:
    data = store.evaluation_state.settings.model_dump()
    data.update(payload.model_dump(exclude_unset=True))
    store.evaluation_state.settings = EvaluationSettings(**data)
    return store.evaluation_state.settings
