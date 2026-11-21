"""Typed data contracts and lineage primitives.

These models represent the canonical, extensible payloads exchanged between
nodes. They preserve provenance and allow artifact-backed large data without
lossy implicit transformations. Algorithm/provider specifics stay outside.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class DataType(str, Enum):
    DOCUMENT = "document"
    DOCUMENT_COLLECTION = "document_collection"
    TEXT = "text"
    CHUNK = "chunk"
    CHUNK_COLLECTION = "chunk_collection"
    EMBEDDING = "embedding"
    EMBEDDING_COLLECTION = "embedding_collection"
    QUERY = "query"
    RETRIEVED_CANDIDATE = "retrieved_candidate"
    RETRIEVED_CANDIDATE_COLLECTION = "retrieved_candidate_collection"
    CONTEXT = "context"
    PROMPT = "prompt"
    GENERATED_ANSWER = "generated_answer"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    VIDEO_FRAME = "video_frame"
    TEMPORAL_SEGMENT = "temporal_segment"
    TABLE = "table"
    METADATA = "metadata"
    NUMERIC_SCORE = "numeric_score"
    EVALUATION_RESULT = "evaluation_result"
    JSON = "json"
    ANY = "any"


class SourceRef(BaseModel):
    """Reference to an origin/source entity (file, dataset, URI, connector item)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str | None = None
    source_type: str | None = None
    uri: str | None = None
    path: str | None = None
    title: str | None = None
    dataset_id: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(BaseModel):
    """Reference to externally stored content (MinIO/filesystem/object store)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str
    uri: str | None = None
    storage: str | None = None  # e.g. s3|minio|local
    content_type: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Provenance(BaseModel):
    """Origin and transformation provenance for a payload."""

    model_config = ConfigDict(extra="forbid")

    producer_node_id: str | None = None
    producer_node_version: str | None = None
    producer_execution_id: str | None = None
    algorithm: str | None = None
    algorithm_version: str | None = None
    parent_ids: list[str] = Field(default_factory=list)
    source: SourceRef | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: dict[str, Any] = Field(default_factory=dict)


class LineageRecord(BaseModel):
    """Append-only lineage step/event for inspectability."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    node_id: str | None = None
    step: str
    detail: str | None = None
    input_ids: list[str] = Field(default_factory=list)
    output_ids: list[str] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataEnvelope(BaseModel):
    """Base envelope for all typed payloads."""

    model_config = ConfigDict(extra="allow")

    id: str
    data_type: DataType
    artifact: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance | None = None
    lineage: list[LineageRecord] = Field(default_factory=list)


class Document(DataEnvelope):
    data_type: DataType = DataType.DOCUMENT
    content: str | None = None
    title: str | None = None
    mime_type: str | None = None
    source: SourceRef | None = None
    pages: int | None = None
    language: str | None = None


class Text(DataEnvelope):
    data_type: DataType = DataType.TEXT
    content: str
    format: str | None = None


class Chunk(DataEnvelope):
    data_type: DataType = DataType.CHUNK
    content: str | None = None
    document_id: str | None = None
    index: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    page: int | None = None
    tokens: int | None = None
    source: SourceRef | None = None


class Embedding(DataEnvelope):
    data_type: DataType = DataType.EMBEDDING
    vector: list[float] | None = None
    dimensions: int | None = None
    model: str | None = None
    item_id: str | None = None  # chunk/document/query id
    normalized: bool | None = None
    dtype: str | None = None


class Query(DataEnvelope):
    data_type: DataType = DataType.QUERY
    text: str
    embedding: Embedding | None = None
    intent: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievedCandidate(DataEnvelope):
    data_type: DataType = DataType.RETRIEVED_CANDIDATE
    content: str | None = None
    chunk_id: str | None = None
    document_id: str | None = None
    score: float | None = None
    rank: int | None = None
    source: SourceRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)  # dense/sparse/rerank etc.


class Context(DataEnvelope):
    data_type: DataType = DataType.CONTEXT
    text: str | None = None
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    token_count: int | None = None
    strategy: str | None = None


class Prompt(DataEnvelope):
    data_type: DataType = DataType.PROMPT
    text: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    template_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class GeneratedAnswer(DataEnvelope):
    data_type: DataType = DataType.GENERATED_ANSWER
    text: str
    model: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str | None = None


class Table(DataEnvelope):
    data_type: DataType = DataType.TABLE
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] | None = None
    schema_info: dict[str, Any] = Field(default_factory=dict)


class NumericScore(DataEnvelope):
    data_type: DataType = DataType.NUMERIC_SCORE
    name: str
    value: float
    scale: str | None = None


class EvaluationResult(DataEnvelope):
    data_type: DataType = DataType.EVALUATION_RESULT
    metric: str
    score: float | None = None
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T", bound=DataEnvelope)


class TypedCollection(DataEnvelope, Generic[T]):
    """Generic typed collection preserving element lineage."""

    items: list[T] = Field(default_factory=list)
    count: int | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.count is None:
            self.count = len(self.items)


class DocumentCollection(TypedCollection[Document]):
    data_type: DataType = DataType.DOCUMENT_COLLECTION


class ChunkCollection(TypedCollection[Chunk]):
    data_type: DataType = DataType.CHUNK_COLLECTION


class EmbeddingCollection(TypedCollection[Embedding]):
    data_type: DataType = DataType.EMBEDDING_COLLECTION


class RetrievedCandidateCollection(TypedCollection[RetrievedCandidate]):
    data_type: DataType = DataType.RETRIEVED_CANDIDATE_COLLECTION
