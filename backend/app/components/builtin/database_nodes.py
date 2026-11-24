"""Nodi di connessione ai database, generati dal catalogo dichiarativo.

Un nodo per tipo di database (Qdrant, PostgreSQL, MongoDB, ...). La modalità
`local`/`remote` e il target `embedded`/`localhost`/`docker`/`ip` determinano
quali campi sono visibili; porta, protocollo, DSN, host Docker e nomi predefiniti
sono derivati dal catalogo e non chiesti all'utente.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

import httpx
from pydantic import BaseModel

from app.api.v1.schemas.models import NodeDefinition, ParamDefinition, PortDefinition
from app.components import algorithms as alg
from app.components.database_catalog import (
    CATALOG,
    ConnectionConfig,
    ConnectionMode,
    ConnectionTarget,
    DatabaseFamily,
    DatabaseSpec,
    FieldKind,
    derive_connection,
    get_spec,
    node_fields,
)
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

_PARAM_TYPE_MAP: dict[FieldKind, ParameterType] = {
    FieldKind.TEXT: ParameterType.TEXT,
    FieldKind.NUMBER: ParameterType.NUMBER,
    FieldKind.PASSWORD: ParameterType.SECRET_REF,
    FieldKind.SELECT: ParameterType.SELECT,
    FieldKind.PATH: ParameterType.TEXT,
}

_UI_TYPE_MAP: dict[FieldKind, str] = {
    FieldKind.TEXT: "text",
    FieldKind.NUMBER: "number",
    FieldKind.PASSWORD: "text",
    FieldKind.SELECT: "select",
    FieldKind.PATH: "text",
}

_DISTANCES = {"cosine": "Cosine", "dot": "Dot", "euclid": "Euclid"}


class ProbeResult(BaseModel):
    ok: bool
    detail: str
    latency_ms: float = 0.0


def node_id(database_id: str) -> str:
    return f"db-{database_id}"


def _config_values(config: NodeConfig) -> dict[str, Any]:
    return dict(config.values or {})


def _connection_from_config(spec: DatabaseSpec, values: dict[str, Any]) -> ConnectionConfig:
    return derive_connection(
        spec.id,
        values.get("mode") or ConnectionMode.LOCAL.value,
        values.get("target") or None,
        values,
    )


def _default_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _port(pid: str, label: str, data_type: str, type_label: str, color: str, *, direction: PortDirection, required: bool = False) -> PortSpec:
    return PortSpec(
        id=pid,
        name=label,
        direction=direction,
        data_types=[data_type],
        required=required,
        description=type_label,
        ui={"label": label, "typeLabel": type_label, "color": color},
    )


def _api_port(pid: str, label: str, data_type: str, type_label: str, color: str, *, required: bool = False) -> PortDefinition:
    return PortDefinition(id=pid, label=label, dataType=data_type, typeLabel=type_label, color=color, required=required)  # type: ignore[arg-type]


def _inputs(spec: DatabaseSpec) -> list[PortSpec]:
    if spec.family is not DatabaseFamily.VECTOR:
        return []
    return [_port("in_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF", direction=PortDirection.INPUT)]


def _outputs(spec: DatabaseSpec) -> list[PortSpec]:
    if spec.family is DatabaseFamily.VECTOR:
        return [
            _port("out_index", "Index", "json", "IndexRef", "#F0B45C", direction=PortDirection.OUTPUT),
            _port("out_connection", "Connessione", "json", "ConnectionRef", "#35D99B", direction=PortDirection.OUTPUT),
        ]
    return [
        _port("out_documents", "Documenti", "documents", "Document[]", "#39D6D0", direction=PortDirection.OUTPUT),
        _port("out_connection", "Connessione", "json", "ConnectionRef", "#35D99B", direction=PortDirection.OUTPUT),
    ]


def _api_inputs(spec: DatabaseSpec) -> list[PortDefinition]:
    if spec.family is not DatabaseFamily.VECTOR:
        return []
    return [_api_port("in_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF")]


def _api_outputs(spec: DatabaseSpec) -> list[PortDefinition]:
    if spec.family is DatabaseFamily.VECTOR:
        return [
            _api_port("out_index", "Index", "json", "IndexRef", "#F0B45C"),
            _api_port("out_connection", "Connessione", "json", "ConnectionRef", "#35D99B"),
        ]
    return [
        _api_port("out_documents", "Documenti", "documents", "Document[]", "#39D6D0"),
        _api_port("out_connection", "Connessione", "json", "ConnectionRef", "#35D99B"),
    ]


def _category(spec: DatabaseSpec) -> str:
    return "Vector Databases" if spec.family is DatabaseFamily.VECTOR else "Databases"


def _target_options_by_mode(spec: DatabaseSpec) -> dict[str, list[str]]:
    return {
        mode.value: [target.value for target in spec.targets_for(mode)]
        for mode in ConnectionMode
        if spec.targets_for(mode)
    }


def node_spec(database_id: str) -> NodeSpec:
    spec = get_spec(database_id)
    parameters: list[ParameterSpec] = []
    for field in node_fields(spec):
        parameters.append(
            ParameterSpec(
                key=field.key,
                label=field.label,
                type=_PARAM_TYPE_MAP[field.kind],
                description=field.help or None,
                required=field.required,
                default=field.default,
                options=[str(option) for option in field.options],
                visible_when=field.visible_when,
                secret=field.kind is FieldKind.PASSWORD,
                ui={
                    "derived": field.derived,
                    "optionsByMode": _target_options_by_mode(spec) if field.key == "target" else None,
                },
            )
        )
    return NodeSpec(
        id=node_id(database_id),
        name=f"{spec.name} connection",
        description=spec.description,
        category=_category(spec),
        kind="vector-store" if spec.family is DatabaseFamily.VECTOR else "source",
        accent=spec.accent,
        inputs=_inputs(spec),
        outputs=_outputs(spec),
        parameters=parameters,
        tags=["database", spec.family.value, spec.id, "connection"],
        documentation=(
            f"{spec.description} Modalità local/remote con target embedded, localhost, Docker o IP. "
            "Porta, protocollo e DSN sono derivati dal tipo di database."
            + (f" {spec.notes}" if spec.notes else "")
        ),
        limitations=[],
    )


def database_node_definitions() -> list[NodeDefinition]:
    """Definizioni API per tutte le famiglie di database del catalogo."""

    definitions: list[NodeDefinition] = []
    for spec in CATALOG:
        params: list[ParamDefinition] = []
        for field in node_fields(spec):
            params.append(
                ParamDefinition(
                    key=field.key,
                    label=field.label,
                    type=_UI_TYPE_MAP[field.kind],  # type: ignore[arg-type]
                    defaultValue=_default_value(field.default),
                    help=field.help or None,
                    options=[str(option) for option in field.options] if field.options else None,
                    required=field.required,
                    secret=field.kind is FieldKind.PASSWORD,
                    derived=field.derived,
                    visibleWhen=field.visible_when,
                    optionsByMode=_target_options_by_mode(spec) if field.key == "target" else None,
                )
            )
        definitions.append(
            NodeDefinition(
                id=node_id(spec.id),
                name=f"{spec.name} connection",
                category=_category(spec),  # type: ignore[arg-type]
                kind="vector-store" if spec.family is DatabaseFamily.VECTOR else "source",
                description=spec.description,
                summary=f"Collega {spec.name} (locale o remoto) e restituisce una connessione utilizzabile nella pipeline.",
                documentation=(
                    f"{spec.description} La configurazione viene derivata dal tipo di database: "
                    "porta, protocollo, host Docker e nomi predefiniti non vanno compilati."
                ),
                accent=spec.accent,
                inputs=_api_inputs(spec),
                outputs=_api_outputs(spec),
                params=params,
                tags=["database", spec.family.value, spec.id, "connection"],
                version="1.0.0",
            )
        )
    return definitions


async def probe_connection(connection: ConnectionConfig) -> ProbeResult:
    """Verifica reale e senza SDK: HTTP health, TCP connect o file/SQLite."""

    started = time.perf_counter()
    if connection.missing:
        return ProbeResult(ok=False, detail=f"Campi mancanti: {', '.join(connection.missing)}")

    def finish(ok: bool, detail: str) -> ProbeResult:
        return ProbeResult(ok=ok, detail=detail, latency_ms=round((time.perf_counter() - started) * 1000, 2))

    if connection.target is ConnectionTarget.EMBEDDED:
        if not connection.path:
            return finish(False, "Percorso locale non configurato")
        path = Path(connection.path).expanduser()
        if connection.database == "sqlite" and path.exists():
            try:
                with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                    db.execute("SELECT 1").fetchone()
                return finish(True, f"SQLite OK · {path}")
            except sqlite3.Error as exc:
                return finish(False, f"SQLite non leggibile: {exc}")
        if path.exists():
            return finish(True, f"Percorso presente · {path}")
        return finish(False, f"Percorso non trovato: {path} (crea il database o correggi il percorso)")

    if connection.scheme.startswith("http"):
        health = get_spec(connection.database).health_path or ""
        url = f"{connection.url}{health}"
        try:
            async with httpx.AsyncClient(timeout=3.0, verify=False, follow_redirects=True) as client:
                response = await client.get(url)
            if response.status_code < 500:
                detail = f"HTTP {response.status_code} · {url}"
                if response.status_code in (401, 403):
                    detail += " (autenticazione richiesta)"
                return finish(True, detail)
            return finish(False, f"HTTP {response.status_code} · {url}")
        except (httpx.HTTPError, OSError) as exc:
            return finish(False, f"HTTP non raggiungibile: {exc}")

    if not connection.host or not connection.port:
        return finish(False, "Host o porta non risolti")
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(connection.host, connection.port), timeout=3.0
        )
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass
        return finish(True, f"TCP OK · {connection.host}:{connection.port}")
    except (OSError, asyncio.TimeoutError) as exc:
        return finish(False, f"TCP non raggiungibile: {exc}")


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _metadata(value: Any) -> dict[str, Any]:
    meta = _get(value, "metadata", None)
    return dict(meta) if isinstance(meta, dict) else {}


def _json_safe(value: Any) -> Any:
    """Rende serializzabile un payload Qdrant anche con modelli Pydantic annidati."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _json_safe(dump())
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float)):
        return enum_value
    return str(value)


def _build_index(embeddings: Any, collection: str, distance: str) -> dict[str, Any]:
    items_in = embeddings if isinstance(embeddings, (list, tuple)) else [embeddings]
    items: list[dict[str, Any]] = []
    dimensions = 0
    for index, embedding in enumerate(items_in):
        if embedding is None:
            continue
        vector = [float(value) for value in (_get(embedding, "vector") or [])]
        dimensions = max(dimensions, len(vector))
        meta = _metadata(embedding)
        items.append(
            {
                "id": str(_get(embedding, "id") or f"emb_{index}"),
                "item_id": _get(embedding, "item_id"),
                "vector": vector,
                "content": meta.get("content") or _get(embedding, "content"),
                "document_id": meta.get("document_id"),
                "chunk_id": meta.get("chunk_id") or _get(embedding, "item_id"),
                "title": meta.get("title"),
                "source": meta.get("source"),
                "metadata": alg.compact_metadata(meta),
            }
        )
    return {"collection": collection, "distance": distance, "dimensions": dimensions, "count": len(items), "items": items}


async def _upsert_qdrant(connection: ConnectionConfig, index: dict[str, Any], distance: str) -> int:
    """Upsert reale via REST: nessun SDK obbligatorio."""

    collection = index["collection"]
    # Qdrant accetta i nomi con l'iniziale maiuscola (Cosine, Dot, Euclid).
    metric = _DISTANCES.get(distance.lower(), "Cosine")
    limit = min(int(index["count"]), 256)
    points = []
    for item in index["items"][:limit]:
        identifier = item["id"]
        try:
            point_id: str | int = int(identifier)
        except (TypeError, ValueError):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection}:{identifier}"))
        payload = {
            key: _json_safe(value)
            for key, value in item.items()
            if key not in ("id", "vector") and value is not None
        }
        points.append({"id": point_id, "vector": item["vector"], "payload": payload})
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        created = await client.put(
            f"{connection.url}/collections/{collection}",
            json={"vectors": {"size": max(index["dimensions"], 1), "distance": metric}},
        )
        if created.status_code not in (200, 201, 409):
            raise RuntimeError(f"Qdrant: creazione collection fallita (HTTP {created.status_code}: {created.text[:200]})")
        upsert = await client.put(
            f"{connection.url}/collections/{collection}/points?wait=true", json={"points": points}
        )
        if upsert.status_code not in (200, 202):
            raise RuntimeError(f"Qdrant: upsert fallito (HTTP {upsert.status_code}: {upsert.text[:200]})")
    return limit


def _rows_to_documents(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        values = dict(row)
        content = next(
            (values[key] for key in ("content", "text", "body", "chunk") if values.get(key) is not None),
            "",
        )
        documents.append(
            {
                "id": str(values.get("id") or f"row_{index}"),
                "title": str(values.get("title") or values.get("name") or f"row_{index}"),
                "content": str(content),
                "source": values.get("source") or values.get("url") or f"db://row/{index}",
                "metadata": {
                    key: value
                    for key, value in values.items()
                    if key not in ("content", "text", "body", "chunk")
                },
            }
        )
    return documents


async def _read_rows(connection: ConnectionConfig, query: str) -> list[dict[str, Any]]:
    if connection.scheme == "sqlite" and connection.path:
        path = Path(connection.path).expanduser()
        if not path.exists():
            raise ValueError(f"File SQLite non trovato: {path}")
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(query).fetchall()
        return _rows_to_documents([dict(row) for row in rows])

    if connection.scheme.startswith(("postgresql", "mysql", "mssql", "oracle", "duckdb")):
        from sqlalchemy import create_engine, text

        engine = create_engine(connection.private_url, pool_pre_ping=True)
        try:
            with engine.connect() as db:
                result = db.execute(text(query))
                keys = list(result.keys())
                rows = [dict(zip(keys, row, strict=False)) for row in result.fetchall()]
        finally:
            engine.dispose()
        return _rows_to_documents(rows)

    raise ValueError(f"Lettura query non ancora disponibile per {connection.name}: usa il nodo come ConnectionRef")


class DatabaseNode(NodeImplementation):
    """Implementazione generica: una istanza per ogni database del catalogo."""

    def __init__(self, database_id: str) -> None:
        self.database_id = database_id
        self._spec = node_spec(database_id)
        self._field_labels = {field.key: field.label for field in node_fields(get_spec(database_id))}

    def spec(self) -> NodeSpec:
        return self._spec

    def validate_config(self, config: NodeConfig) -> list[str]:
        values = _config_values(config)
        try:
            connection = _connection_from_config(get_spec(self.database_id), values)
        except ValueError as exc:
            return [str(exc)]
        return [
            f"Campo obbligatorio mancante: {self._field_labels.get(key, key)}"
            for key in connection.missing
        ]

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        spec = get_spec(self.database_id)
        values = _config_values(config)
        node = self._spec.id
        try:
            connection = _connection_from_config(spec, values)
        except ValueError as exc:
            return NodeResult(node_id=node, status="failed", errors=[str(exc)])

        if connection.missing:
            labels = ", ".join(self._field_labels.get(key, key) for key in connection.missing)
            return NodeResult(node_id=node, status="failed", errors=[f"Configurazione incompleta: {labels}"])

        probe = await probe_connection(connection)
        if not probe.ok:
            context.log("ERROR", f"{spec.name} non raggiungibile: {probe.detail}")
            return NodeResult(node_id=node, status="failed", errors=[probe.detail], metadata={"probe": probe.model_dump()})

        warnings: list[str] = []
        if "autenticazione richiesta" in probe.detail:
            warnings.append(probe.detail)
        outputs: dict[str, Any] = {"out_connection": connection.public_dict()}
        metrics: dict[str, Any] = {
            "database": spec.id,
            "mode": connection.mode.value,
            "target": connection.target.value,
            "port": connection.port,
            "latency_ms": probe.latency_ms,
        }

        if spec.family is DatabaseFamily.VECTOR:
            embeddings = inputs.get("in_embedding") or []
            distance = str(values.get("distance") or "Cosine")
            collection = str(values.get("collection") or spec.default_collection or "documents")
            index = await asyncio.to_thread(_build_index, embeddings, collection, distance)
            if connection.database == "qdrant" and index["count"] and connection.target is not ConnectionTarget.EMBEDDED:
                try:
                    written = await _upsert_qdrant(connection, index, distance)
                    metrics["upserted"] = written
                    warnings.append(f"Qdrant REST: {written} vettori scritti nella collection {collection}.")
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    return NodeResult(node_id=node, status="failed", errors=[str(exc)], outputs=outputs, metrics=metrics)
            else:
                warnings.append(
                    f"Nessun adapter di scrittura attivo per {spec.name}: "
                    "l'indice resta disponibile solo per questa esecuzione."
                )
            outputs["out_index"] = index
            metrics.update({"vectors": index["count"], "dimensions": index["dimensions"], "collection": collection})
            ref = await context.store_artifact(
                f"index_{connection.database}", index, metadata={"collection": collection, "vectors": index["count"]}
            )
            context.log("INFO", f"{spec.name}: {probe.detail}; indice con {index['count']} vettori")
            return NodeResult(
                node_id=node,
                outputs=outputs,
                output_artifacts={"out_index": ref},
                metrics=metrics,
                logs=[f"{spec.name}: {probe.detail}"],
                warnings=warnings,
                metadata={"connection": connection.public_dict()},
            )

        query = str(values.get("query") or "").strip()
        documents: list[dict[str, Any]] = []
        if query:
            try:
                documents = await _read_rows(connection, query)
            except Exception as exc:  # SQLAlchemy/DBAPI errors depend on the installed driver
                return NodeResult(node_id=node, status="failed", errors=[str(exc)], outputs=outputs, metrics=metrics)
            metrics["documents"] = len(documents)
        else:
            warnings.append("Nessuna query impostata: il nodo restituisce solo la connessione.")
        outputs["out_documents"] = documents
        ref = await context.store_artifact(
            f"rows_{connection.database}", documents, metadata={"database": spec.id, "rows": len(documents)}
        )
        context.log("INFO", f"{spec.name}: {probe.detail}; {len(documents)} documenti")
        return NodeResult(
            node_id=node,
            outputs=outputs,
            output_artifacts={"out_documents": ref},
            metrics=metrics,
            logs=[f"{spec.name}: {probe.detail}"],
            warnings=warnings,
            metadata={"connection": connection.public_dict()},
        )


DATABASE_IMPLEMENTATIONS: tuple[NodeImplementation, ...] = tuple(DatabaseNode(spec.id) for spec in CATALOG)


def register_database_implementations(registry: Any) -> int:
    registered = 0
    for implementation in DATABASE_IMPLEMENTATIONS:
        node = implementation.spec().id
        if registry.get_implementation(node) is None:
            registry.register_implementation(implementation, source="builtin")
            registered += 1
    return registered


__all__ = [
    "DATABASE_IMPLEMENTATIONS",
    "DatabaseNode",
    "ProbeResult",
    "database_node_definitions",
    "node_id",
    "node_spec",
    "probe_connection",
    "register_database_implementations",
]
