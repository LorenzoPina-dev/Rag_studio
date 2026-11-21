from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_node_implementation_endpoint() -> None:
    response = client.get("/api/v1/nodes/semantic-chunker/implementation")
    assert response.status_code == 200
    body = response.json()
    assert body["definitionId"] == "semantic-chunker"
    assert "semantic_chunks" in body["implementation"]
    assert "def " in body["source"]
    assert body["reference"] is True
    assert body["inputs"] and body["outputs"]

    missing = client.get("/api/v1/nodes/does-not-exist/implementation")
    assert missing.status_code == 404


def test_custom_node_create_endpoint() -> None:
    seed = client.get("/api/v1/custom-nodes").json()[0]
    payload = {**seed, "id": "cn_test_created", "slug": "test_created", "basedOn": "builtin:semantic-chunker"}

    created = client.post("/api/v1/custom-nodes", json=payload)
    assert created.status_code == 200
    assert created.json()["id"] == "cn_test_created"

    fetched = client.get("/api/v1/custom-nodes/cn_test_created")
    assert fetched.status_code == 200
    assert fetched.json()["basedOn"] == "builtin:semantic-chunker"
