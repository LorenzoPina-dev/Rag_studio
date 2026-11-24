"""Knowledge-graph nodes for the ESG RAG track.

Two complementary nodes:

* ``kg-extractor`` builds a typed entity/relation graph with a real LLM (or,
  explicitly, with the deterministic reference extractor) from documents;
* ``kg-writer`` persists that graph to Neo4j through its HTTP transaction API,
  so the KG survives the run instead of living only in a JSON artifact.

Both emit/consume the same graph shape used by ``graph-builder`` /
``graph-retriever``: ``{"nodes": [...], "edges": [...], "count": n}``.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from typing import Any

import httpx

from app.components import algorithms as alg
from app.core.config import neo4j_password as resolve_neo4j_password
from app.domain.contracts.data import Prompt
from app.domain.contracts.node import (
    NodeConfig,
    NodeImplementation,
    NodeResult,
    NodeSpec,
    ParameterSpec,
    ParameterType,
    PortDirection,
    PortSpec,
)

_ENTITY_TYPES = ("company", "metric", "standard", "framework", "year", "location", "initiative", "entity")
_PLACEHOLDER_VALUES = {"...", "…", ".", "..", "-", "--", "n/a", "na", "none", "null", "example", "tbd", "todo"}


def _meaningful(value: Any) -> bool:
    """Reject placeholder labels copied verbatim from the extraction prompt."""
    text = str(value or "").strip().strip("\"'")
    return bool(text) and text.lower() not in _PLACEHOLDER_VALUES


def _port(
    port_id: str,
    label: str,
    data_type: str,
    type_label: str,
    color: str,
    *,
    direction: PortDirection,
    required: bool = False,
) -> PortSpec:
    return PortSpec(
        id=port_id,
        name=label,
        direction=direction,
        data_types=[data_type],
        required=required,
        ui={"label": label, "typeLabel": type_label, "color": color},
    )


def _param(
    key: str,
    label: str,
    param_type: ParameterType,
    default: Any,
    *,
    options: list[Any] | None = None,
    help: str | None = None,
) -> ParameterSpec:
    return ParameterSpec(key=key, label=label, type=param_type, default=default, options=list(options or []), description=help)


def _documents(inputs: Mapping[str, Any]) -> list[Any]:
    value = inputs.get("in_documents") or []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _json_objects(value: str) -> list[str]:
    """Estrae gli oggetti JSON bilanciati, ignorando testo e stringhe interne."""
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(value):
        if start is None:
            if char == "{":
                start, depth = index, 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                objects.append(value[start : index + 1])
                start = None
    return objects


def _parse_json_object(raw: Any) -> dict[str, Any]:
    value = str(raw or "").strip()
    value = re.sub(r"^```(?:json)?", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"```$", "", value).strip()
    merged: dict[str, Any] = {}
    chunks = _json_objects(value)
    for chunk in chunks:
        try:
            payload = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            for key, item in payload.items():
                merged.setdefault(key, item)
    if not merged:
        raise ValueError("il modello non ha restituito un oggetto JSON")
    return merged


def normalize_graph(payload: Mapping[str, Any], source: str = "llm") -> dict[str, Any]:
    """Validate and deduplicate a graph payload into the canonical shape."""
    nodes: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for item in payload.get("nodes") or []:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        node_id = str(item.get("id") or label).strip()
        if not _meaningful(node_id) or node_id in by_id:
            continue
        if not _meaningful(label):
            label = node_id
        node_type = str(item.get("type") or "entity").strip()
        node = {
            "id": node_id,
            "label": label or node_id,
            "type": node_type if node_type in _ENTITY_TYPES else "entity",
            "source": str(item.get("source") or source),
        }
        by_id[node_id] = node
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for item in payload.get("edges") or []:
        if not isinstance(item, Mapping):
            continue
        head = str(item.get("source") or "").strip()
        tail = str(item.get("target") or "").strip()
        label = str(item.get("label") or "relates to").strip() or "relates to"
        if not _meaningful(head) or not _meaningful(tail):
            continue
        if not _meaningful(label):
            label = "relates to"
        if (head, tail, label) in seen_edges:
            continue
        seen_edges.add((head, tail, label))
        for endpoint in (head, tail):
            if endpoint not in by_id:
                node = {"id": endpoint, "label": endpoint, "type": "entity", "source": source}
                by_id[endpoint] = node
                nodes.append(node)
        try:
            weight = float(item.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        edges.append({"source": head, "target": tail, "label": label, "weight": weight})

    return {"nodes": nodes, "edges": edges, "count": len(nodes)}


def build_prompt(texts: list[str], taxonomy: str) -> str:
    corpus = "\n\n---\n\n".join(texts)
    return (
        "Sei un analista di documentazione non finanziaria. Estrai entità e relazioni "
        "rilevanti per la tassonomia ESG dal testo fornito.\n"
        f"Tassonomia di riferimento: {taxonomy or 'ESRS e GRI'}.\n"
        "Tipi di entità ammessi: " + ", ".join(_ENTITY_TYPES) + ".\n"
        "Rispondi SOLO con un oggetto JSON valido, senza commenti né markdown, nella forma:\n"
        '{"nodes":[{"id":"...","label":"...","type":"company","source":"..."}],'
        '"edges":[{"source":"...","target":"...","label":"...","weight":1.0}]}\n'
        "Usa id stabili e descrittivi. Non inventare metriche non presenti nel testo.\n\n"
        f"TESTO:\n{corpus}"
    )


def cypher_statements(graph: Mapping[str, Any], *, clear: bool = False) -> list[dict[str, Any]]:
    """Build parameterised Neo4j statements from a canonical graph payload."""
    statements: list[dict[str, Any]] = []
    if clear:
        statements.append({"statement": "MATCH (n) DETACH DELETE n", "parameters": {}})
    nodes = [dict(item) for item in (graph.get("nodes") or []) if isinstance(item, Mapping)]
    edges = [dict(item) for item in (graph.get("edges") or []) if isinstance(item, Mapping)]
    if nodes:
        statements.append(
            {
                "statement": (
                    "UNWIND $nodes AS n MERGE (e:Entity {id: n.id}) "
                    "SET e.label = n.label, e.type = n.type, e.source = n.source"
                ),
                "parameters": {
                    "nodes": [
                        {
                            "id": str(node.get("id") or ""),
                            "label": str(node.get("label") or ""),
                            "type": str(node.get("type") or "entity"),
                            "source": str(node.get("source") or "llm"),
                        }
                        for node in nodes
                    ]
                },
            }
        )
    if edges:
        statements.append(
            {
                "statement": (
                    "UNWIND $edges AS r MATCH (a:Entity {id: r.source}), (b:Entity {id: r.target}) "
                    "MERGE (a)-[rel:RELATES_TO {label: r.label}]->(b) SET rel.weight = r.weight"
                ),
                "parameters": {
                    "edges": [
                        {
                            "source": str(edge.get("source") or ""),
                            "target": str(edge.get("target") or ""),
                            "label": str(edge.get("label") or "relates to"),
                            "weight": float(edge.get("weight", 1.0) or 1.0),
                        }
                        for edge in edges
                    ]
                },
            }
        )
    return statements


class KGExtractorNode(NodeImplementation):
    """Extract a typed ESG knowledge graph with a real LLM."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="kg-extractor",
            name="ESG knowledge graph extractor",
            description="Extract ESG entities and relations with an LLM (or explicit reference mode).",
            category="Enrichment",
            kind="processor",
            accent="#9D7BFF",
            inputs=[
                _port("in_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.INPUT, required=True)
            ],
            outputs=[
                _port("out_graph", "Graph", "json", "KnowledgeGraph", "#9D7BFF", direction=PortDirection.OUTPUT),
                _port("out_metrics", "Metrics", "json", "Json", "#5B7CFA", direction=PortDirection.OUTPUT),
            ],
            parameters=[
                _param("provider", "Provider", ParameterType.SELECT, "auto",
                       options=["auto", "huggingface", "ollama", "openai", "reference"],
                       help="reference = estrattore deterministico, non un modello."),
                _param("model", "Model", ParameterType.TEXT, ""),
                _param("taxonomy", "Taxonomy", ParameterType.TEXT, "ESRS E1-E5, S1-S4, G1-G5 e GRI Standards"),
                _param("maxDocs", "Max documents", ParameterType.NUMBER, 12),
                _param("maxCharsPerDoc", "Max chars per document", ParameterType.NUMBER, 12000),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        documents = _documents(inputs)
        if not documents:
            return NodeResult(node_id="kg-extractor", status="failed", errors=["Nessun documento in ingresso per il grafo."])
        provider = str(config.get("provider") or "auto")
        records = [alg.as_dict(item) for item in documents]
        max_docs = max(1, int(float(config.get("maxDocs", 12) or 12)))
        max_chars = max(500, int(float(config.get("maxCharsPerDoc", 12000) or 12000)))

        if provider == "reference":
            from app.components.builtin.advanced_nodes import graph_from_records as build_reference_graph

            graph = await asyncio.to_thread(
                lambda: normalize_graph(build_reference_graph(records), source="reference")
            )
            resolution_name, model_name = "reference", "regex-relations"
        else:
            texts = [str(alg.text(item) or "")[:max_chars] for item in records[:max_docs]]
            texts = [value for value in texts if value.strip()]
            if not texts:
                return NodeResult(node_id="kg-extractor", status="failed", errors=["I documenti non contengono testo estraibile."])
            from app.providers import resolver

            try:
                resolution = await resolver.aresolve_generator(provider, str(config.get("model") or "") or None)
                raw = await resolution.implementation.generate(
                    Prompt(id="kg_extraction", text=build_prompt(texts, str(config.get("taxonomy") or ""))),
                    config={"temperature": 0.0, "max_tokens": 512},
                )
                payload = await asyncio.to_thread(_parse_json_object, raw.text)
            except Exception as exc:  # noqa: BLE001 - modelli diversi sollevano errori diversi
                message = f"Estrazione KG fallita: {type(exc).__name__}: {exc}"
                context.log("ERROR", message)
                return NodeResult(node_id="kg-extractor", status="failed", errors=[message])
            graph = await asyncio.to_thread(normalize_graph, payload, source="llm")
            resolution_name, model_name = resolution.provider, resolution.model

        if hasattr(context, "store_artifact"):
            await context.store_artifact(
                "kg_esg", graph, metadata={"nodes": graph["count"], "edges": len(graph["edges"]), "provider": resolution_name}
            )
        metrics = {
            "nodes": graph["count"],
            "edges": len(graph["edges"]),
            "provider": resolution_name,
            "model": model_name,
            "reference": resolution_name == "reference",
        }
        message = f"ESG graph: {metrics['nodes']} entità, {metrics['edges']} relazioni ({resolution_name}/{model_name})"
        context.log("INFO", message)
        return NodeResult(
            node_id="kg-extractor",
            outputs={"out_graph": graph, "out_metrics": metrics},
            metrics=metrics,
            logs=[message],
            warnings=["Estrazione reference: pattern deterministici, non un modello addestrato."] if resolution_name == "reference" else [],
        )


class KGWriterNode(NodeImplementation):
    """Persist a graph to Neo4j through the HTTP transaction endpoint."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="kg-writer",
            name="Neo4j graph writer",
            description="Write an ESG graph to Neo4j with parameterised Cypher (HTTP transaction API).",
            category="Databases",
            kind="processor",
            accent="#F0B45C",
            inputs=[_port("in_graph", "Graph", "json", "KnowledgeGraph", "#9D7BFF", direction=PortDirection.INPUT, required=True)],
            outputs=[
                _port("out_graph", "Graph", "json", "KnowledgeGraph", "#9D7BFF", direction=PortDirection.OUTPUT),
                _port("out_connection", "Connection", "json", "ConnectionRef", "#35D99B", direction=PortDirection.OUTPUT),
            ],
            parameters=[
                _param("host", "Host", ParameterType.TEXT, "127.0.0.1"),
                _param("httpPort", "HTTP port", ParameterType.NUMBER, 7474),
                _param("database", "Database", ParameterType.TEXT, "neo4j"),
                _param("user", "User", ParameterType.TEXT, "neo4j"),
                _param("password", "Password (or NEO4J_PASSWORD)", ParameterType.SECRET_REF, ""),
                _param("clear", "Cancella il grafo prima di scrivere", ParameterType.BOOLEAN, False),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        graph = inputs.get("in_graph")
        if not isinstance(graph, Mapping):
            return NodeResult(node_id="kg-writer", status="failed", errors=["Grafo in ingresso non valido."])
        statements = await asyncio.to_thread(
            cypher_statements, graph, clear=bool(config.get("clear", False))
        )
        host = str(config.get("host") or "127.0.0.1")
        port = int(float(config.get("httpPort", 7474) or 7474))
        database = str(config.get("database") or "neo4j")
        user = str(config.get("user") or "neo4j")
        password = resolve_neo4j_password(config)
        endpoint = f"http://{host}:{port}/db/{database}/tx/commit"
        connection = {"kind": "neo4j", "host": host, "port": port, "database": database, "authenticated": bool(password)}

        if not statements:
            warning = "Grafo vuoto: nessuna scrittura eseguita su Neo4j."
            context.log("WARN", warning)
            return NodeResult(
                node_id="kg-writer",
                outputs={"out_graph": dict(graph), "out_connection": connection},
                metrics={"nodes": 0, "edges": 0, "written": False},
                warnings=[warning],
            )
        auth = (user, password) if password else None
        try:
            async with httpx.AsyncClient(timeout=20.0, auth=auth) as client:
                response = await client.post(endpoint, json={"statements": statements})
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            message = f"Scrittura Neo4j fallita: {type(exc).__name__}: {exc}"
            context.log("ERROR", message)
            return NodeResult(node_id="kg-writer", status="failed", errors=[message], outputs={"out_connection": connection})

        nodes = len(graph.get("nodes") or [])
        edges = len(graph.get("edges") or [])
        metrics = {"nodes": nodes, "edges": edges, "statements": len(statements), "written": True, "database": database}
        message = f"Neo4j: {nodes} entità e {edges} relazioni scritte in {database}"
        context.log("INFO", message)
        return NodeResult(
            node_id="kg-writer",
            outputs={"out_graph": dict(graph), "out_connection": connection},
            metrics=metrics,
            logs=[message],
        )


KG_IMPLEMENTATIONS: tuple[NodeImplementation, ...] = (KGExtractorNode(), KGWriterNode())


def register_kg_implementations(registry: Any) -> int:
    registered = 0
    for implementation in KG_IMPLEMENTATIONS:
        node_id = implementation.spec().id
        if registry.get_implementation(node_id) is None:
            registry.register_implementation(implementation)
            registered += 1
    return registered
