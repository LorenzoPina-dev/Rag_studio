from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.schemas.models import Model, ModelResources, ModelTestResponse, ModelsData, Provider
from app.infrastructure.memory import store

router = APIRouter()


class ModelCreate(BaseModel):
    name: str
    provider: str
    type: str


class ModelTestRequest(BaseModel):
    prompt: str


@router.get("/models", response_model=ModelsData)
def list_models() -> ModelsData:
    return store.models_data()


@router.get("/models/providers", response_model=list[Provider])
def list_providers() -> list[Provider]:
    return store.providers


@router.get("/models/resources", response_model=ModelResources)
def get_model_resources() -> ModelResources:
    return store.models_data().resources


@router.post("/models", response_model=Model)
def register_model(payload: ModelCreate) -> Model:
    model = Model(
        id=store._id("m"),
        name=payload.name,
        provider=payload.provider,
        type=payload.type,  # type: ignore[arg-type]
        context="—",
        status="ready",
        description=f"Registered model {payload.name}.",
        architecture="—",
        parameters="—",
        dimensions="—",
        maxSequence="—",
        precision="—",
        device="—",
        memory="—",
        license="—",
        usedBy=0,
        local=payload.provider.lower() != "openai",
    )
    store.models.insert(0, model)
    return model


@router.patch("/models/{model_id}", response_model=Model)
def update_model(model_id: str, payload: dict) -> Model:
    for i, m in enumerate(store.models):
        if m.id == model_id:
            data = m.model_dump()
            data.update(payload or {})
            updated = Model(**data)
            store.models[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models/{model_id}/test", response_model=ModelTestResponse)
def test_model(model_id: str, payload: ModelTestRequest) -> ModelTestResponse:
    model = next((m for m in store.models if m.id == model_id), None)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    snippet = payload.prompt.strip()[:120] or "test prompt"
    return ModelTestResponse(
        modelId=model_id,
        output=f"[{model.name}] Test response for: {snippet}",
        latencyMs=142,
        tokens=max(12, len(payload.prompt.split())),
        cost=0.0004 if not model.local else 0.0,
    )
