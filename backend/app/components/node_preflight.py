"""Test preventivi dei componenti remoti o non interni di una pipeline.

L'obiettivo è rispondere in pochi secondi: ogni verifica ha un timeout duro e non
avvia l'esecuzione della pipeline. Per i modelli viene eseguita una micro-inferenza
(1 testo, 1 candidato o pochi token generati), sufficiente a convincersi che
provider, modello e configurazione siano utilizzabili.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.components.builtin import database_nodes
from app.components.database_catalog import ConnectionMode, ConnectionTarget, derive_connection, get_spec
from app.core.config import neo4j_password as resolve_neo4j_password
from app.domain.contracts.data import Prompt, Query, RetrievedCandidate
from app.providers import resolver
from app.providers import settings as provider_settings
from app.providers._common import sanitize

# I nodi con un provider/modello esterno. La chiave è il definition id, il valore
# indica dove leggere provider e modello nella configurazione del nodo.
MODEL_NODES: dict[str, tuple[str, str]] = {
    "provider-embeddings": ("provider", "model"),
    "provider-reranker": ("provider", "model"),
    "prompt-generation": ("provider", "model"),
    "kg-extractor": ("provider", "model"),
    "hybrid-retrieval": ("embeddingProvider", "embeddingModel"),
}

MODEL_CAPABILITIES: dict[str, str] = {
    "provider-embeddings": "embeddings",
    "provider-reranker": "reranking",
    "prompt-generation": "generation",
    "kg-extractor": "generation",
    "hybrid-retrieval": "embeddings",
}

GRAPH_NODES = frozenset({"kg-writer"})

DEFAULT_TIMEOUT_SECONDS = 20.0
_timeout_lock = asyncio.Lock()


def timeout_seconds() -> float:
    """Timeout duro di ogni test, configurabile via NODE_TEST_TIMEOUT_SECONDS."""

    try:
        value = float(os.environ.get("NODE_TEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


def is_testable(definition_id: str) -> bool:
    """True per i componenti che hanno una verifica preventiva definita."""

    return definition_id.startswith("db-") or definition_id in MODEL_NODES or definition_id in GRAPH_NODES


def _result(
    *,
    ok: bool,
    detail: str,
    category: str,
    latency_ms: float,
    supported: bool = True,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "detail": detail,
        "category": category,
        "latencyMs": round(latency_ms, 2),
        "supported": supported,
        "provider": provider,
        "model": model,
    }


async def _test_database(database_id: str, config: dict[str, Any], timeout: float) -> dict[str, Any]:
    spec = get_spec(database_id)
    mode_value = str(config.get("mode") or "")
    target_value = str(config.get("target") or "")
    mode = ConnectionMode(mode_value) if mode_value else (
        ConnectionMode.LOCAL
        if ConnectionMode.LOCAL in [item for item in ConnectionMode if spec.targets_for(item)]
        else ConnectionMode.REMOTE
    )
    target = ConnectionTarget(target_value) if target_value else spec.targets_for(mode)[0]
    connection = derive_connection(spec.id, mode, target, config)
    probe = await asyncio.wait_for(database_nodes.probe_connection(connection), timeout=timeout)
    return _result(
        ok=probe.ok,
        detail=probe.detail,
        category="database",
        latency_ms=probe.latency_ms,
        provider=spec.id,
        model=f"{mode.value}/{target.value}",
    )


async def _test_neo4j(config: dict[str, Any], timeout: float) -> dict[str, Any]:
    host = str(config.get("host") or "127.0.0.1")
    port = int(float(config.get("httpPort", 7474) or 7474))
    database = str(config.get("database") or "neo4j")
    user = str(config.get("user") or "neo4j")
    password = resolve_neo4j_password(config)
    endpoint = f"http://{host}:{port}/db/{database}/tx/commit"
    auth = (user, password) if password else None

    async with httpx.AsyncClient(timeout=min(5.0, timeout), auth=auth) as client:
        response = await client.post(
            endpoint,
            json={"statements": [{"statement": "RETURN 1 AS preflight"}]},
        )
        response.raise_for_status()
        payload = response.json()

    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        raise RuntimeError(f"Neo4j ha restituito errori Cypher: {errors}")
    return _result(
        ok=True,
        detail=f"Neo4j OK · {database}@{host}:{port}",
        category="graph",
        latency_ms=0.0,
        provider="neo4j",
        model=database,
    )


async def _test_model(definition_id: str, config: dict[str, Any]) -> dict[str, Any]:
    provider_key, model_key = MODEL_NODES[definition_id]
    provider = str(config.get(provider_key) or "auto")
    model = str(config.get(model_key) or "") or None
    capability = MODEL_CAPABILITIES[definition_id]

    if provider == "reference":
        return _result(
            ok=True,
            detail="Modalità reference locale: nessun provider remoto da verificare.",
            category="model",
            latency_ms=0.0,
            provider="reference",
            model="reference",
        )

    def resolve() -> Any:
        if capability == "embeddings":
            return resolver.resolve_embeddings(provider, model)
        if capability == "reranking":
            return resolver.resolve_reranker(provider, model)
        return resolver.resolve_generator(provider, model)

    resolution = await asyncio.to_thread(resolve)

    if capability == "embeddings":
        vectors = await resolution.implementation.embed_texts(
            ["preflight ESG"], config={"source": "node-test"}
        )
        dimensions = len(vectors[0].vector) if vectors and vectors[0].vector else 0
        if not dimensions:
            raise RuntimeError("Il modello di embedding non ha restituito vettori utilizzabili.")
        detail = f"Embedding OK · {resolution.provider}/{resolution.model} · {dimensions} dimensioni"
    elif capability == "reranking":
        ranked = await resolution.implementation.rerank(
            Query(id="preflight_query", text="Reporting ESG"),
            [RetrievedCandidate(id="preflight_candidate", content="Documento ESG di prova.")],
            config={},
        )
        if not ranked:
            raise RuntimeError("Il modello di reranking non ha restituito candidati.")
        detail = f"Reranking OK · {resolution.provider}/{resolution.model}"
    else:
        answer = await resolution.implementation.generate(
            Prompt(id="preflight_prompt", text="Rispondi esattamente con OK."),
            config={"temperature": 0.0, "max_tokens": 8},
        )
        text = str(getattr(answer, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Il modello di generazione non ha restituito testo.")
        detail = f"Generazione OK · {resolution.provider}/{resolution.model} · {len(text)} caratteri"

    return _result(
        ok=True,
        detail=detail,
        category="model",
        latency_ms=0.0,
        provider=resolution.provider,
        model=resolution.model,
    )


async def _dispatch(definition_id: str, config: dict[str, Any], timeout: float) -> dict[str, Any]:
    if definition_id.startswith("db-"):
        return await _test_database(definition_id[3:], config, timeout)
    if definition_id in GRAPH_NODES:
        return await _test_neo4j(config, timeout)
    if definition_id in MODEL_NODES:
        return await _test_model(definition_id, config)
    return _result(
        ok=False,
        detail=f"Nessun test automatico definito per '{definition_id}' (componente interno).",
        category="internal",
        latency_ms=0.0,
        supported=False,
    )


async def test_node(definition_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Esegue il test di un nodo con timeout duro; non solleva eccezioni al caller."""

    started = time.perf_counter()
    values = dict(config or {})
    timeout = timeout_seconds()
    category = "model" if definition_id in MODEL_NODES else (
        "database" if definition_id.startswith("db-") else "graph" if definition_id in GRAPH_NODES else "internal"
    )
    try:
        async with _timeout_lock:
            result = await asyncio.wait_for(_dispatch(definition_id, values, timeout), timeout=timeout)
    except asyncio.TimeoutError:
        return _result(
            ok=False,
            detail=f"Timeout dopo {timeout:g}s durante il test di '{definition_id}'.",
            category=category,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001 - ogni provider solleva errori diversi
        detail = sanitize(exc, provider_settings.effective_settings().openai_api_key)
        return _result(
            ok=False,
            detail=f"Test non riuscito: {detail}",
            category=category,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
    if not result.get("latencyMs"):
        result["latencyMs"] = round((time.perf_counter() - started) * 1000, 2)
    return result
