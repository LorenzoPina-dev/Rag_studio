"""Query input must expose the same editable parameters in API, spec and runtime."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.components.algorithms import DEFAULT_QUERY
from app.components.builtin.reference_nodes import QueryInputNode
from app.domain.contracts.node import NodeConfig
from app.main import app

client = TestClient(app)


class FakeContext:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def log(self, level: str, message: str, **fields: object) -> None:
        self.logs.append(message)


def test_nodes_api_exposes_query_parameter() -> None:
    definitions = client.get("/api/v1/nodes").json()
    definition = next(item for item in definitions if item["id"] == "query-input")
    params = {param["key"]: param for param in definition["params"]}

    assert "query" in params
    assert params["query"]["defaultValue"] == DEFAULT_QUERY
    assert "placeholder" in params


def test_query_input_spec_exposes_query_parameter() -> None:
    params = QueryInputNode().spec().parameter_map

    assert "query" in params
    assert params["query"].default == DEFAULT_QUERY
    assert "placeholder" in params


async def test_query_input_execute_uses_configured_query() -> None:
    result = await QueryInputNode().execute(
        {},
        NodeConfig(values={"query": "Qual è il fatturato 2025?", "placeholder": "Ask a question..."}),
        FakeContext(),
    )

    assert result.outputs["out_query"].text == "Qual è il fatturato 2025?"
