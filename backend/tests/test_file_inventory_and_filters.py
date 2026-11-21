"""File inventory, per-type filters and hybrid branch execution."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.components import algorithms as alg
from app.components.corpus import load_documents_for_dataset
from app.components.dataset_connectors import fetch_documents, inspect_local_files, inspect_s3_files
from app.core.bootstrap import container
from app.domain.contracts.pipeline import GraphEdge, GraphNode, PipelineGraph
from app.engine import PipelineExecutor
from app.infrastructure import dataset_store
from app.main import app


PDF_MARKER = "PDF_BRANCH_MARKER"
TXT_MARKER = "TEXT_BRANCH_MARKER"


@pytest.fixture(autouse=True)
def isolated_dataset_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "DATA_PATH", tmp_path / "datasets.json")
    monkeypatch.setattr(dataset_store, "_datasets", None)
    yield
    monkeypatch.setattr(dataset_store, "_datasets", None)


def _make_pdf(text: str) -> bytes:
    """Create a minimal valid one-page PDF without external dependencies."""
    content = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@pytest.fixture
def mixed_folder(tmp_path):
    folder = tmp_path / "sources"
    folder.mkdir()
    (folder / "report.pdf").write_bytes(_make_pdf(PDF_MARKER))
    (folder / "notes.txt").write_text(TXT_MARKER, encoding="utf-8")
    (folder / "records.json").write_text(
        json.dumps([{"id": "j1", "title": "JSON record", "source": "records.json", "content": "json body"}]),
        encoding="utf-8",
    )
    (folder / "picture.png").write_bytes(b"not text")
    return folder


def test_local_connector_extracts_pdf_and_inventory_lists_every_file(mixed_folder):
    documents = fetch_documents("Local files", str(mixed_folder))
    by_type = {item.get("fileType"): item for item in documents}

    assert by_type["pdf"]["content"].startswith("PDF_BRANCH")
    assert by_type["txt"]["content"] == TXT_MARKER

    inventory = inspect_local_files(str(mixed_folder))
    assert {item["name"] for item in inventory} == {
        "report.pdf", "notes.txt", "records.json", "picture.png"
    }
    indexed = {item["name"]: item["indexed"] for item in inventory}
    assert indexed["report.pdf"] is True
    assert indexed["picture.png"] is False


def test_sync_exposes_inventory_and_document_source_filters(mixed_folder):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "mixed", "sourceType": "Local files", "path": str(mixed_folder)},
        )
        assert created.status_code == 201, created.text
        dataset_id = created.json()["id"]

        synced = client.post(f"/api/v1/datasets/{dataset_id}/sync")
        assert synced.status_code == 200, synced.text
        dataset = synced.json()
        assert len(dataset["files"]) == 4
        assert dataset["chunks"] == 0  # chunking belongs to the pipeline, not the dataset
        assert dataset["documents"] == 3  # only the indexable files
        assert any(file["name"] == "report.pdf" and file["indexed"] for file in dataset["files"])
        assert any(file["name"] == "picture.png" and not file["indexed"] for file in dataset["files"])

        assert dataset["items"] == []  # sync never caches extracted text
        pdf_documents = load_documents_for_dataset(dataset_id, "pdf")
        assert len(pdf_documents) == 1
        assert pdf_documents[0]["content"].startswith("PDF_BRANCH")
        assert load_documents_for_dataset(dataset_id, "text")[0]["fileType"] == "txt"
        assert len(load_documents_for_dataset(dataset_id, file_name="report*")) == 1
        assert len(load_documents_for_dataset(dataset_id, file_name="missing*")) == 0

        filters = alg.config_from_pipeline(
            {
                "nodes": [
                    {
                        "definitionId": "document-source",
                        "kind": "source",
                        "config": {"dataset": dataset_id, "fileTypes": "pdf", "fileName": "report"},
                    }
                ]
            }
        )
        assert filters["file_types"] == "pdf"
        assert filters["file_name"] == "report"


def test_sync_is_a_metadata_scan_and_loader_reads_the_connector_at_runtime(mixed_folder):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "scan", "sourceType": "Local files", "path": str(mixed_folder)},
        )
        dataset_id = created.json()["id"]
        synced = client.post(f"/api/v1/datasets/{dataset_id}/sync").json()

        assert synced["items"] == []
        assert synced["documents"] == 3
        raw = dataset_store.DATA_PATH.read_text(encoding="utf-8")
        assert PDF_MARKER not in raw
        assert TXT_MARKER not in raw

        # A file added after sync is available to the pipeline without caching text.
        (mixed_folder / "later.txt").write_text("LATEST_MARKER", encoding="utf-8")
        assert any(
            item["content"] == "LATEST_MARKER"
            for item in load_documents_for_dataset(dataset_id, "txt")
        )
        assert all(file.name != "later.txt" for file in dataset_store.get_dataset(dataset_id).files)

        client.post(f"/api/v1/datasets/{dataset_id}/sync")
        assert any(file.name == "later.txt" for file in dataset_store.get_dataset(dataset_id).files)


def test_s3_sync_lists_objects_without_downloading_them(monkeypatch):
    class FakeMinio:
        def __init__(self, *args, **kwargs):
            pass

        def list_objects(self, bucket, prefix="", recursive=False):
            return [
                SimpleNamespace(object_name="docs/", size=0),
                SimpleNamespace(object_name="docs/report.pdf", size=2048),
                SimpleNamespace(object_name="docs/notes.md", size=64),
            ]

        def get_object(self, *args, **kwargs):
            raise AssertionError("sync must not download object content")

    monkeypatch.setitem(sys.modules, "minio", SimpleNamespace(Minio=FakeMinio))
    inventory = inspect_s3_files(
        "s3://bucket/docs/",
        {"endpoint": "s3.example.com", "accessKey": "a", "secretKey": "b"},
    )

    assert [file["name"] for file in inventory] == ["report.pdf", "notes.md"]
    assert inventory[0]["path"] == "s3://bucket/docs/report.pdf"
    assert inventory[0]["size"] == 2048
    assert inventory[0]["indexed"] is True


def test_dataset_list_sends_previews_not_full_pdf_text(mixed_folder):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "name": "large",
                "sourceType": "Local files",
                "path": str(mixed_folder),
                "items": [
                    {
                        "id": "long",
                        "title": "Long doc",
                        "source": "long.txt",
                        "content": "x" * 5000,
                    }
                ],
            },
        )
        dataset_id = created.json()["id"]

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        preview = next(item for item in listed.json()["datasets"] if item["id"] == dataset_id)
        assert len(preview["items"][0]["content"]) == 240

        full = client.get(f"/api/v1/datasets/{dataset_id}")
        assert len(full.json()["items"][0]["content"]) == 5000

        # The preview must be a copy: runtime/export still need the whole text.
        assert len(dataset_store.get_dataset(dataset_id).items[0].content) == 5000


@pytest.mark.asyncio
async def test_two_filtered_sources_merge_into_one_branch(mixed_folder):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "hybrid", "sourceType": "Local files", "path": str(mixed_folder)},
        )
        dataset_id = created.json()["id"]
        client.post(f"/api/v1/datasets/{dataset_id}/sync")

    def node(node_id: str, definition: str, kind: str, config: dict) -> GraphNode:
        return GraphNode(
            id=node_id,
            definition_id=definition,
            name=node_id,
            kind=kind,
            config=config,
        )

    def edge(source: str, target: str, target_port: str) -> GraphEdge:
        return GraphEdge(
            id=f"{source}_{target}_{target_port}",
            source_node_id=source,
            source_port_id="out_documents",
            target_node_id=target,
            target_port_id=target_port,
        )

    graph = PipelineGraph(
        nodes=[
            node("src_pdf", "document-source", "source", {"dataset": dataset_id, "fileTypes": "pdf"}),
            node("src_text", "document-source", "source", {"dataset": dataset_id, "fileTypes": "text"}),
            node("merge", "merge-documents", "merge", {}),
            node("chunk", "semantic-chunking", "chunking", {"chunkStrategy": "fixed"}),
        ],
        edges=[
            edge("src_pdf", "merge", "in_documents_a"),
            edge("src_text", "merge", "in_documents_b"),
            edge("merge", "chunk", "in_documents"),
        ],
    )
    executor = PipelineExecutor(
        container.node_registry,
        artifact_store=container.artifact_store,
        secret_resolver=container.secret_resolver,
        provider_registry=container.provider_registry,
    )
    run = await executor.execute(graph, execution_id="hybrid_branches", pipeline_id="hybrid")

    assert run.status == "completed", [(item.node_id, item.error) for item in run.outcomes if item.error]
    outcomes = {outcome.node_id: outcome for outcome in run.outcomes}
    assert outcomes["src_pdf"].result.metrics["documents"] == 1
    assert outcomes["src_text"].result.metrics["documents"] == 1
    assert outcomes["merge"].result.metrics["documents"] == 2
    assert outcomes["chunk"].status == "completed"
