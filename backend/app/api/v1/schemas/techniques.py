"""Schemi Pydantic per il catalogo machine-readable delle tecniche RAG."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.techniques_catalog import Status


class TechniqueSummary(BaseModel):
    """Rappresentazione compatta di una tecnica, usata nei raggruppamenti."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    phase: str
    status: Status


class TechniqueResponse(TechniqueSummary):
    """Rappresentazione completa di una tecnica del catalogo."""

    description: str
    implementation: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)


class TechniqueCategorySummary(BaseModel):
    """Categoria funzionale con conteggio e tecniche appartenenti."""

    category: str
    slug: str
    count: int
    techniques: list[TechniqueSummary] = Field(default_factory=list)


class TechniquePhaseSummary(BaseModel):
    """Fase della pipeline con numero, slug e conteggio."""

    phase: str
    number: int
    slug: str
    count: int


class TechniqueCatalogResponse(BaseModel):
    """Risposta alle query sul catalogo, con filtri applicati e aggregati globali."""

    total: int
    summary: dict[str, Any]
    techniques: list[TechniqueResponse] = Field(default_factory=list)
