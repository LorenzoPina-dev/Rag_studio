"""Visual component metadata must survive chunking, indexing and retrieval."""

from __future__ import annotations

from typing import Any

from app.components import algorithms as alg
from app.components.builtin import reference_nodes
from app.components.builtin.database_nodes import _build_index
from app.domain.contracts.data import ArtifactRef, Chunk, Embedding, SourceRef
from app.domain.contracts.node import NodeConfig


class FakeContext:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.artifacts: dict[str, Any] = {}

    def log(self, level: str, message: str, **fields: object) -> None:
        self.logs.append(message)

    def is_cancelled(self) -> bool:
        return False

    async def store_artifact(self, name: str, data: object, **kwargs: object) -> ArtifactRef:
        self.artifacts[name] = data
        return ArtifactRef(artifact_id=name, uri=f"memory://{name}")


def _visual_metadata() -> dict[str, Any]:
    return {
        "title": "report",
        "source": "/data/report.pdf",
        "hasVisuals": True,
        "componentCounts": {"images": 1, "figures": 1},
        "enrichment": {"tables": 0, "images": 1, "figures": 1, "descriptionMode": "reference"},
        "data": "SECRET_RAW_IMAGE_BYTES",
    }


def test_chunk_documents_keep_only_compact_visual_metadata():
    document = {
        "id": "doc_1",
        "content": "Le vendite sono cresciute nel 2024.",
        "title": "report",
        "source": "/data/report.pdf",
        "metadata": {
            **_visual_metadata(),
            "components": {"images": [{"data": "SECRET"}], "figures": [{"data": "SECRET"}]},
        },
    }

    chunks = alg.chunk_documents([document])

    assert chunks
    metadata = chunks[0]["metadata"]
    assert metadata["componentCounts"] == {"images": 1, "figures": 1}
    assert metadata["enrichment"]["descriptionMode"] == "reference"
    assert metadata["hasVisuals"] is True
    assert "components" not in metadata
    assert "data" not in metadata


async def test_document_source_preserves_extracted_components(monkeypatch):
    payload = [
        {
            "id": "doc_1",
            "title": "report",
            "source": "/data/report.pdf",
            "content": "Report 2024",
            "fileType": "pdf",
            "pages": 3,
            "components": {"tables": [], "images": [{"kind": "image"}], "figures": []},
        }
    ]
    monkeypatch.setattr(reference_nodes, "load_documents_for_dataset", lambda *args, **kwargs: payload)

    result = await reference_nodes.DocumentSourceNode().execute(
        {}, NodeConfig(values={"dataset": "ds"}), FakeContext()
    )

    document = result.outputs["out_documents"][0]
    assert document.metadata["components"] == payload[0]["components"]
    assert document.metadata["pages"] == 3
    assert document.metadata["mime_type"] == "application/pdf"


async def test_visual_metadata_survives_chunks_index_and_retrieval():
    chunk = Chunk(
        id="chunk_1",
        content="Grafico vendite: ricavi in crescita nel 2024.",
        document_id="doc_1",
        index=0,
        source=SourceRef(uri="/data/report.pdf", title="report"),
        metadata=_visual_metadata(),
    )

    embedding_result = await reference_nodes.HashEmbeddingsReferenceNode().execute(
        {"in_text": [chunk]}, NodeConfig(values={}), FakeContext()
    )
    embedding = embedding_result.outputs["out_embedding"][0]
    assert embedding.metadata["componentCounts"] == {"images": 1, "figures": 1}
    assert "data" not in embedding.metadata

    index_result = await reference_nodes.InMemoryIndexReferenceNode().execute(
        {"in_embedding": [embedding]}, NodeConfig(values={"collection": "visual"}), FakeContext()
    )
    index = index_result.outputs["out_index"]
    assert index["items"][0]["metadata"]["componentCounts"] == {"images": 1, "figures": 1}

    candidates = alg.retrieve("grafico vendite", index["items"], top_k=1)
    assert candidates
    assert candidates[0]["metadata"]["componentCounts"] == {"images": 1, "figures": 1}
    assert candidates[0]["metadata"]["enrichment"]["descriptionMode"] == "reference"
    assert candidates[0]["metadata"]["algorithm"] == "hybrid"
    assert "data" not in candidates[0]["metadata"]


def test_database_index_builder_preserves_visual_metadata():
    embedding = Embedding(
        id="emb_1",
        vector=[0.1, 0.2],
        item_id="chunk_1",
        metadata=_visual_metadata(),
    )

    index = _build_index([embedding], "visual", "Cosine")

    assert index["items"][0]["metadata"]["componentCounts"] == {"images": 1, "figures": 1}
    assert "data" not in index["items"][0]["metadata"]
