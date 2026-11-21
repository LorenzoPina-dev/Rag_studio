"""Storage infrastructure (artifacts, blobs)."""

from .minio_store import MinioArtifactStore

__all__ = ["MinioArtifactStore"]
