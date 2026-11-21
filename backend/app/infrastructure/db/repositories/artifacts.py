"""Persistence-backed artifact reference repository.

Artifacts themselves live in an object store (memory/MinIO); this repository
keeps the durable references and metadata so execution artifacts stay
inspectable after a process restart.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.data import ArtifactRef

from ..models.artifact import ArtifactRecord
from .base import SessionProvider


def _ref_from_row(row: ArtifactRecord) -> ArtifactRef:
    metadata = dict(row.meta or {})
    if row.name and not metadata.get("name"):
        metadata["name"] = row.name
    return ArtifactRef(
        artifact_id=row.id,
        uri=row.uri,
        storage=row.storage,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        checksum=row.checksum,
        metadata=metadata,
    )


class SqlAlchemyArtifactRepository:
    """Stores artifact references/metadata for executions and node runs."""

    def __init__(self, session: Session | None = None, session_factory: sessionmaker[Session] | None = None):
        self._sp = SessionProvider(session=session, session_factory=session_factory)

    async def save_ref(
        self,
        ref: ArtifactRef,
        *,
        execution_id: str | None = None,
        node_execution_id: str | None = None,
        kind: str | None = None,
        name: str | None = None,
    ) -> ArtifactRef:
        metadata = dict(ref.metadata or {})
        resolved_execution = execution_id or metadata.get("execution_id")
        resolved_node = node_execution_id or metadata.get("node_execution_id")
        resolved_kind = kind or metadata.get("kind")
        resolved_name = name or metadata.get("name")
        storage = ref.storage or "memory"
        uri = ref.uri or f"{storage}://artifacts/{ref.artifact_id}"

        with self._sp.scope() as s:
            row = s.get(ArtifactRecord, ref.artifact_id)
            if row is None:
                row = ArtifactRecord(id=ref.artifact_id, uri=uri)
            row.execution_id = resolved_execution
            row.node_execution_id = resolved_node
            row.name = resolved_name
            row.kind = resolved_kind
            row.uri = uri
            row.storage = storage
            row.content_type = ref.content_type
            row.size_bytes = ref.size_bytes
            row.checksum = ref.checksum
            row.meta = metadata
            s.add(row)
            s.flush()
        return ref

    async def save_many(
        self,
        refs: Sequence[ArtifactRef],
        *,
        execution_id: str | None = None,
    ) -> list[ArtifactRef]:
        return [await self.save_ref(ref, execution_id=execution_id) for ref in refs]

    async def get(self, artifact_id: str) -> ArtifactRef | None:
        with self._sp.scope() as s:
            row = s.get(ArtifactRecord, artifact_id)
            return _ref_from_row(row) if row is not None else None

    async def list_for_execution(self, execution_id: str) -> list[ArtifactRef]:
        with self._sp.scope() as s:
            rows = (
                s.execute(
                    select(ArtifactRecord)
                    .where(ArtifactRecord.execution_id == execution_id)
                    .order_by(ArtifactRecord.created_at.asc(), ArtifactRecord.id.asc())
                )
                .scalars()
                .all()
            )
            return [_ref_from_row(r) for r in rows]

    async def delete_for_execution(self, execution_id: str) -> int:
        with self._sp.scope() as s:
            result = s.execute(delete(ArtifactRecord).where(ArtifactRecord.execution_id == execution_id))
            return int(result.rowcount or 0)
