"""Endpoint REST per il catalogo esaustivo delle tecniche RAG."""

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.techniques import (
    TechniqueCatalogResponse,
    TechniqueCategorySummary,
    TechniquePhaseSummary,
    TechniqueResponse,
    TechniqueSummary,
)
from app.components import techniques_catalog as catalog
from app.components.techniques_catalog import Status, Technique

router = APIRouter(prefix="/techniques")


def _summary(technique: Technique) -> TechniqueSummary:
    """Projeta una tecnica nello schema compatto."""
    return TechniqueSummary(
        id=technique.id,
        name=technique.name,
        category=technique.category,
        phase=technique.phase,
        status=technique.status,
    )


def _response(technique: Technique) -> TechniqueResponse:
    """Projeta una tecnica nello schema completo."""
    return TechniqueResponse(
        id=technique.id,
        name=technique.name,
        category=technique.category,
        phase=technique.phase,
        status=technique.status,
        description=technique.description,
        implementation=technique.implementation,
        tags=list(technique.tags),
        parameters=dict(technique.parameters),
    )


@router.get("", response_model=TechniqueCatalogResponse)
def list_techniques(
    phase: str | None = Query(default=None, description="Numero, slug o nome della fase"),
    category: str | None = Query(default=None, description="Slug o nome della categoria"),
    status: Status | None = Query(default=None, description="Stato di implementazione"),
    search: str | None = Query(default=None, description="Ricerca testuale libera"),
) -> TechniqueCatalogResponse:
    """Restituisce le tecniche filtrate, con i conteggi aggregati del catalogo."""
    techniques = catalog.list_techniques(
        phase=phase, category=category, status=status, search=search
    )
    return TechniqueCatalogResponse(
        total=len(techniques),
        summary=catalog.catalog_summary(),
        techniques=[_response(technique) for technique in techniques],
    )


@router.get("/categories", response_model=list[TechniqueCategorySummary])
def list_categories() -> list[TechniqueCategorySummary]:
    """Restituisce tutte le categorie funzionali con le relative tecniche."""
    result: list[TechniqueCategorySummary] = []
    for category in catalog.CATEGORIES:
        techniques = catalog.list_techniques(category=category)
        result.append(
            TechniqueCategorySummary(
                category=category,
                slug=catalog.category_slug(category),
                count=len(techniques),
                techniques=[_summary(technique) for technique in techniques],
            )
        )
    return result


@router.get("/phases", response_model=list[TechniquePhaseSummary])
def list_phases() -> list[TechniquePhaseSummary]:
    """Restituisce le 15 fasi della pipeline con i rispettivi conteggi."""
    return [
        TechniquePhaseSummary(
            phase=phase,
            number=int(phase.split(" ", 1)[0]),
            slug=catalog.phase_slug(phase),
            count=len(catalog.list_techniques(phase=phase)),
        )
        for phase in catalog.PHASES
    ]


@router.get("/{technique_id}", response_model=TechniqueResponse)
def get_technique(technique_id: str) -> TechniqueResponse:
    """Restituisce una singola tecnica dato il suo ID slug."""
    technique = catalog.get_technique(technique_id)
    if technique is None:
        raise HTTPException(status_code=404, detail="Technique not found")
    return _response(technique)
