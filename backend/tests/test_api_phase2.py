from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_openapi():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    spec = app.openapi()
    assert "/api/v1/projects" in spec["paths"]
    assert "/api/v1/executions/{execution_id}/stream" in spec["paths"]


def test_core_endpoints_shapes():
    assert client.get("/api/v1/system/status").status_code == 200
    assert client.get("/api/v1/workspace").status_code == 200

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert "metrics" in body and "projects" in body and "pipelines" in body

    projects = client.get("/api/v1/projects")
    assert projects.status_code == 200
    assert isinstance(projects.json(), list) and projects.json()

    pipelines = client.get("/api/v1/pipelines")
    assert pipelines.status_code == 200
    assert isinstance(pipelines.json(), list) and pipelines.json()

    nodes = client.get("/api/v1/nodes")
    assert nodes.status_code == 200
    assert isinstance(nodes.json(), list) and nodes.json()

    catalog = client.get("/api/v1/nodes/catalog")
    assert catalog.status_code == 200
    assert isinstance(catalog.json(), list) and catalog.json()


def test_pipeline_validate_and_execution_results():
    pipeline = client.get("/api/v1/pipelines/pl_hybrid_rag")
    assert pipeline.status_code == 200
    pdata = pipeline.json()
    assert pdata["id"] == "pl_hybrid_rag"
    assert "nodes" in pdata and "edges" in pdata

    validation = client.post("/api/v1/pipelines/pl_hybrid_rag/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    results = client.get("/api/v1/executions/run_2486/results")
    assert results.status_code == 200
    rdata = results.json()
    assert rdata["executionId"] == "run_2486"
    assert "documents" in rdata and "generatedAnswer" in rdata


def test_domain_collections():
    for path in [
        "/api/v1/datasets",
        "/api/v1/models",
        "/api/v1/executions",
        "/api/v1/evaluations",
        "/api/v1/experiments",
        "/api/v1/custom-nodes/templates",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
