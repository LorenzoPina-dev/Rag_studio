"""Test della famiglia di nodi database: catalogo, derivazione, esecuzione, API."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.schemas.models import NodeDefinition
from app.components.builtin import database_nodes
from app.components.builtin.database_nodes import (
    DATABASE_IMPLEMENTATIONS,
    DatabaseNode,
    ProbeResult,
    database_node_definitions,
)
from app.components.database_catalog import (
    ConnectionConfig,
    ConnectionMode,
    ConnectionTarget,
    DatabaseFamily,
    catalog_entries,
    derive_connection,
    get_spec,
    node_fields,
)
from app.core.bootstrap import container
from app.domain.contracts.data import ArtifactRef
from app.domain.contracts.node import NodeConfig
from app.infrastructure.memory import store
from app.main import app

client = TestClient(app)


class FakeContext:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def log(self, level: str, message: str, **fields: object) -> None:
        self.logs.append(message)

    def is_cancelled(self) -> bool:
        return False

    async def store_artifact(self, name: str, data: object, **kwargs: object) -> ArtifactRef:
        return ArtifactRef(artifact_id=f"art_{name}", uri=f"memory://{name}")


def test_catalog_covers_all_families_and_modes():
    entries = catalog_entries()
    assert len(entries) == len({entry.id for entry in entries})
    families = {entry.family for entry in entries}
    assert DatabaseFamily.VECTOR in families
    assert DatabaseFamily.RELATIONAL in families
    assert DatabaseFamily.DOCUMENT in families
    assert {entry.id for entry in entries} >= {
        "qdrant", "chroma", "faiss", "pgvector", "postgresql", "sqlite", "mongodb", "redis"
    }
    qdrant = next(entry for entry in entries if entry.id == "qdrant")
    assert qdrant.modes == [ConnectionMode.LOCAL, ConnectionMode.REMOTE]
    assert any(field.key == "collection" for field in qdrant.required_fields)
    assert any(field.key == "port" and field.derived for field in node_fields(get_spec("qdrant")))
    faiss = next(entry for entry in entries if entry.id == "faiss")
    assert faiss.modes == [ConnectionMode.LOCAL]


@pytest.mark.parametrize(
    ("database", "mode", "target", "values", "expected_host", "expected_port"),
    [
        ("qdrant", "local", "localhost", {}, "127.0.0.1", 6333),
        ("qdrant", "local", "docker", {}, "qdrant", 6333),
        ("qdrant", "remote", "ip", {"host": "10.0.0.4"}, "10.0.0.4", 6333),
        ("postgresql", "remote", "docker", {"host": "pg.internal"}, "pg.internal", 5432),
        ("mysql", "local", "docker", {}, "mysql", 3306),
    ],
)
def test_derived_host_and_port(database, mode, target, values, expected_host, expected_port):
    config = derive_connection(database, mode, target, values)
    assert config.host == expected_host
    assert config.port == expected_port
    assert not config.missing or set(config.missing) <= {"username", "password", "database"}


def test_derivation_reports_only_missing_required_fields():
    config = derive_connection("postgresql", "remote", "ip", {"host": "192.168.1.9"})
    assert set(config.missing) == {"username", "password"}
    assert config.url == "postgresql+psycopg://192.168.1.9:5432/documents"

    config = derive_connection(
        "postgresql",
        "remote",
        "ip",
        {"host": "192.168.1.9", "username": "rag", "password": "secret", "database": "docs"},
    )
    assert not config.missing
    assert config.url == "postgresql+psycopg://rag:***@192.168.1.9:5432/docs"
    assert config.private_url == "postgresql+psycopg://rag:secret@192.168.1.9:5432/docs"
    assert "private_url" not in config.public_dict()
    assert config.public_dict()["secrets"]["password"] == "***"


def test_embedded_path_and_invalid_target():
    config = derive_connection("sqlite", "local", "embedded", {})
    assert config.path == "./.ragstudio/ragstudio.sqlite3"
    assert config.url.startswith("sqlite:///")
    with pytest.raises(ValueError, match="non supporta"):
        derive_connection("faiss", "remote", "ip", {"host": "1.2.3.4"})
    with pytest.raises(ValueError, match="Porta"):
        derive_connection("qdrant", "remote", "ip", {"host": "1.2.3.4", "port": "abc"})


def test_node_definitions_and_registry_are_in_sync():
    definitions: list[NodeDefinition] = database_node_definitions()
    assert len(definitions) == len(catalog_entries())
    stored = {definition.id for definition in store.node_definitions}
    assert {definition.id for definition in definitions} <= stored
    registry = container.node_registry
    assert len(DATABASE_IMPLEMENTATIONS) == len(definitions)
    for implementation in DATABASE_IMPLEMENTATIONS:
        definition = next(item for item in definitions if item.id == implementation.spec().id)
        registry_spec = registry.get_spec(definition.id)
        assert registry_spec is not None
        assert registry.get_implementation(definition.id) is implementation
        assert {param.key for param in registry_spec.parameters} == {param.key for param in definition.params}
    qdrant = next(item for item in definitions if item.id == "db-qdrant")
    target = next(param for param in qdrant.params if param.key == "target")
    assert target.optionsByMode is not None
    assert "localhost" in target.optionsByMode["local"]
    assert "ip" in target.optionsByMode["remote"]
    chroma = next(item for item in definitions if item.id == "db-chroma")
    chroma_target = next(param for param in chroma.params if param.key == "target")
    assert "embedded" in chroma_target.optionsByMode["local"]
    mode = next(param for param in qdrant.params if param.key == "mode")
    assert mode.visibleWhen is None
    host = next(param for param in qdrant.params if param.key == "host")
    assert host.visibleWhen == {"target": ["docker", "ip"]}
    assert next(param for param in qdrant.params if param.key == "port").derived is True


def test_validate_config_uses_connection_requirements():
    node = DatabaseNode("qdrant")
    assert node.validate_config(NodeConfig(values={"mode": "remote", "target": "ip"})) == [
        "Campo obbligatorio mancante: IP o hostname"
    ]
    assert node.validate_config(NodeConfig(values={"mode": "local", "target": "docker"})) == []
    postgres = DatabaseNode("postgresql")
    errors = postgres.validate_config(NodeConfig(values={"mode": "local", "target": "localhost"}))
    assert any("Utente" in error for error in errors)
    assert any("Password" in error for error in errors)


async def test_execute_vector_node_uses_real_probe_and_builds_index(monkeypatch):
    monkeypatch.setattr(
        database_nodes,
        "probe_connection",
        _fake_probe(ProbeResult(ok=True, detail="HTTP 200", latency_ms=1.5)),
    )
    upserted: list[int] = []

    async def fake_upsert(config: ConnectionConfig, index: dict[str, object], distance: str) -> int:
        upserted.append(index["count"])
        return int(index["count"])

    monkeypatch.setattr(database_nodes, "_upsert_qdrant", fake_upsert)
    node = DatabaseNode("qdrant")
    embeddings = [{"id": "e1", "vector": [0.1, 0.2], "metadata": {"content": "ciao"}}]
    result = await node.execute(
        {"in_embedding": embeddings},
        NodeConfig(values={"mode": "local", "target": "localhost", "collection": "docs", "distance": "Cosine"}),
        FakeContext(),
    )
    assert result.status == "completed"
    assert result.outputs["out_index"]["count"] == 1
    assert result.outputs["out_index"]["collection"] == "docs"
    assert result.outputs["out_connection"]["url"] == "http://127.0.0.1:6333"
    assert result.metrics["upserted"] == 1
    assert upserted == [1]


async def test_upsert_qdrant_uses_capitalised_distance(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def put(self, url: str, json: dict | None = None):
            calls.append((url, json or {}))
            return SimpleNamespace(status_code=200, text="{}")

    monkeypatch.setattr(database_nodes.httpx, "AsyncClient", FakeClient)
    connection = SimpleNamespace(url="http://qdrant:6333")
    index = {
        "collection": "esg_chunks",
        "dimensions": 2,
        "count": 1,
        "items": [
            {
                "id": "e1",
                "vector": [0.1, 0.2],
                "metadata": {
                    "source": SimpleNamespace(
                        model_dump=lambda: {"uri": "/data/esg/a2a_2023.pdf"}
                    )
                },
            }
        ],
    }
    written = await database_nodes._upsert_qdrant(connection, index, "cosine")
    assert written == 1
    assert calls[0][1]["vectors"]["distance"] == "Cosine"
    payload = calls[1][1]["points"][0]["payload"]
    assert payload["metadata"]["source"]["uri"] == "/data/esg/a2a_2023.pdf"


def _fake_probe(result: ProbeResult):
    async def probe(config: ConnectionConfig) -> ProbeResult:
        return result

    return probe


async def test_execute_reports_connection_failure(monkeypatch):
    monkeypatch.setattr(
        database_nodes,
        "probe_connection",
        _fake_probe(ProbeResult(ok=False, detail="TCP non raggiungibile")),
    )
    result = await DatabaseNode("qdrant").execute(
        {}, NodeConfig(values={"mode": "local", "target": "localhost"}), FakeContext()
    )
    assert result.status == "failed"
    assert "TCP non raggiungibile" in result.errors[0]


async def test_sqlite_embedded_reads_real_rows(tmp_path: Path):
    db_path = tmp_path / "docs.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE documents (id TEXT, title TEXT, content TEXT)")
        db.execute("INSERT INTO documents VALUES ('1', 'Titolo', 'Contenuto reale')")

    node = DatabaseNode("sqlite")
    result = await node.execute(
        {},
        NodeConfig(
            values={
                "mode": "local",
                "target": "embedded",
                "path": str(db_path),
                "query": "SELECT id, title, content FROM documents",
            }
        ),
        FakeContext(),
    )
    assert result.status == "completed"
    assert result.outputs["out_documents"][0]["content"] == "Contenuto reale"
    assert result.metrics["documents"] == 1


def test_api_catalog_derive_and_test(monkeypatch):
    catalog = client.get("/api/v1/databases/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["total"] == len(catalog_entries())

    derived = client.post(
        "/api/v1/databases/derive",
        json={"database": "qdrant", "mode": "local", "target": "docker", "values": {}},
    )
    assert derived.status_code == 200
    body = derived.json()
    assert body["url"] == "http://qdrant:6333"
    assert body["port"] == 6333
    assert body["missing"] == []

    incomplete = client.post(
        "/api/v1/databases/derive",
        json={"database": "postgresql", "mode": "remote", "target": "ip", "values": {"host": "1.2.3.4"}},
    )
    assert incomplete.json()["missing"] == ["username", "password"]

    unknown = client.get("/api/v1/databases/catalog")
    assert unknown.status_code == 200
    missing_db = client.post("/api/v1/databases/derive", json={"database": "nope"})
    assert missing_db.status_code == 404

    monkeypatch.setattr(
        database_nodes,
        "probe_connection",
        _fake_probe(ProbeResult(ok=True, detail="TCP OK", latency_ms=2.0)),
    )
    tested = client.post(
        "/api/v1/databases/test",
        json={"database": "qdrant", "mode": "local", "target": "localhost", "values": {}},
    )
    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert tested.json()["latencyMs"] == 2.0


def test_spec_ids_are_unique_with_builtin_catalog():
    ids = [implementation.spec().id for implementation in DATABASE_IMPLEMENTATIONS]
    assert len(ids) == len(set(ids))
    assert get_spec("qdrant").family is DatabaseFamily.VECTOR
    assert ConnectionTarget.EMBEDDED in get_spec("chroma").targets_for(ConnectionMode.LOCAL)
