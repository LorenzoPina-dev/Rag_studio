# RAG STUDIO Backend Architecture

## Status
- Phase: **5/6 in progress — real in-process execution + reference nodes** (foundation and frontend contracts stable)
- Date: 2026-11-21
- Scope: Backend architecture compatible with the existing React/TypeScript frontend (`frontend/`), mock-adapter behavior, and the requested algorithm-agnostic RAG platform.

## 1. Frontend analysis (existing system)

### 1.1 UI surfaces and capabilities
From `frontend/src/App.tsx`, routes/pages, stores, and API modules:

| Surface | Route | Primary frontend needs |
|---|---|---|
| Dashboard | `/` | Workspace, system status, dashboard metrics/projects/pipelines/activity, search |
| Projects | `/projects` | Project CRUD/listing, project health/metadata |
| Pipelines list | `/pipelines` | Pipeline summaries, create/duplicate/delete/export navigation |
| Pipeline editor | `/pipelines/:pipelineId` | Full pipeline graph (nodes/edges/config), validation, run, save/export, node catalog/definitions |
| Node library | `/nodes` | Node catalog/categories/definitions/docs metadata |
| Custom nodes | `/custom-nodes` | Custom node detail/editor, files/code, params/ports, dependencies, tests, publish/versioning/templates |
| Datasets & sources | `/datasets` | Dataset metrics/list/detail/update, sync/reindex, data sources CRUD/sync, ingestion jobs |
| Models & providers | `/models` | Providers, models registry/resources, register/update/test, provider/model metadata |
| Execution monitor | `/runs/:runId` | Execution state, node runs, logs, metrics, stop/rerun, **real-time progress stream** |
| Intermediate results | `/runs/:runId/results` | Persisted results/artifacts: query, retrieved docs/chunks, lineage, embeddings, generated answer, runtime breakdown |
| Evaluation | `/evaluation` | Evaluation data/runs/settings, run evaluation, report export |
| Experiments | `/experiments` | Experiment list/summary, create, compare, promote |
| Settings | `/settings` | Workspace/configuration surface (frontend-local today; backend must support provider/config persistence) |

### 1.2 Frontend integration facts (must preserve)
- Central client: `frontend/src/api/client.ts`
  - `VITE_API_URL` default `/api/v1`
  - `VITE_USE_MOCKS` default `true` (in-memory mock adapter implements the same contract)
  - JSON REST, `ApiError` with `status/message/detail`, 204 -> `undefined`
- Real-time: `frontend/src/api/executions.api.ts` subscribes via `EventSource('/api/v1/executions/:id/stream')` (SSE) with events `{type,status,node,log,execution}`
- Export actions are currently client-side downloads built from fetched JSON (`pipelinesApi.export`, `evaluationsApi.exportReport`) but backend must provide canonical retrievable resources.
- Types are the de-facto contract: `frontend/src/types/index.ts` (IDs are strings; pipeline nodes carry `definitionId`, `kind`, `config`, typed ports; executions include `nodeRuns`, `logs`, metrics; results include lineage/docs/embedding/runtime; datasets/models/providers/custom nodes/evaluations/experiments shapes are explicit).

### 1.3 Key contract observations
- **Graph model**: `Pipeline {id, projectId, name, description, environment, status, version, updatedAt, nodes[], edges[], lastRun?}`. `PipelineNode` is an instance (`definitionId`, position, config, inputs/outputs, status/duration). `PipelineEdge` has source/target/handles/dataType.
- **Validation**: `POST /pipelines/:id/validate -> {valid, errors[], warnings[], checkedAt}` with issues referencing `nodeId`/severity/message.
- **Execution**: summaries + detail; monitor needs `nodeRuns[]` (status/duration/outputCount/accent), `logs[]` (level/timestamp/node/message), counters/trace/cost/tokens/environment/trigger; `POST /pipelines/:id/run` returns an execution; stop/logs/results/artifacts endpoints exist.
- **Results/inspectability**: `/executions/:id/results` is rich (query, selected/retrieved counts, documents, lineage, node outputs, embedding inspector, runtime breakdown, generated answer/meta). These must be backed by **artifact references/storage**, not giant execution rows.
- **Node registry/catalog**: `/nodes`, `/nodes/catalog` expose definitions/categories/ports/params/docs for UI-driven inspectors/forms.
- **Custom nodes**: detail/update, tests/test-runs, dependencies, publish/version restore, templates; code must run in isolated workers (not FastAPI process).
- **Domain breadth now**: projects/dashboard/search/workspace/system, pipelines, nodes/catalog, datasets/sources/jobs, models/providers/resources, executions/results/artifacts/stream, evaluations, experiments, custom nodes.

## 2. Architectural principles (binding)
- **Algorithm-agnostic core**: DAG engine, APIs, persistence, and frontend never depend on concrete RAG libraries/models/algorithms. Concrete behavior is provided via interfaces/adapters/plugins registered in registries.
- **Style**: modular monolith + separated workers (Celery). Hexagonal/Clean boundaries, Dependency Inversion/SOLID, Repository + Strategy + Plugin patterns, DI at composition root.
- **Layers**:
  1. `domain/` — entities, value objects, contracts, business rules (no FastAPI/SQLAlchemy/Redis/provider SDKs).
  2. `application/` — use cases, orchestration, DTO mapping, transaction boundaries.
  3. `infrastructure/` — DB/ORM, repositories, storage (MinIO/filesystem), queue (Redis/Celery), provider adapters, telemetry exporters.
  4. `api/` (interfaces) — REST routers/schemas, SSE/WebSocket, auth/deps, frontend-facing contracts.
- **Engines/registries isolated**: `engine/` (graph/validation/scheduler/runtime/events/caching) and `registry/` depend on domain contracts, not web/db details.
- **No lossy/implicit transforms**: typed data contracts with provenance/lineage; large payloads stored as artifacts with references.

## 3. Core domain contracts (Phase 1 target)

### 3.1 Node system (generic, UI-driven)
Canonical contracts (Pydantic v2, versioned):
- `NodeSpec`: stable id/slug, name, description, category, tags, icon/accent, documentation, source (`builtin|custom`), status/capabilities/limitations.
- `PortSpec`: port id/name, direction (`in|out`), data type(s), required/optional, multiplicity, description, UI metadata.
- `ParameterSpec`: key, label, type (`text|number|select|boolean|textarea|json|secret-ref` etc.), default, constraints/validation, unit/help/options, visibility/depends-on.
- `NodeConfig`: instance config map validated against `ParameterSpec`.
- `NodeImplementation` (interface): declares spec/ports/params, validates config & inputs, executes -> `NodeResult` (sync/async/stream-capable contract), reports resource hints.
- `NodeRuntime`: execution context (run ids, artifact store, logger/metrics emitter, cancellation token, limits, resolved providers/secrets refs).
- `NodeResult`: typed outputs, metrics, logs/events refs, produced artifact refs, warnings/errors, lineage additions.
- `NodeVersion`: immutable implementation/version metadata + compatibility info.

Static **definitions** (registry/catalog) are separated from **instances** (pipeline graph nodes) and from **executions** (immutable snapshots).

### 3.2 Typed data contracts & lineage
Common payload types (extensible, schema-first): `Document`, `DocumentCollection`, `Text`, `Chunk`, `ChunkCollection`, `Embedding`, `EmbeddingCollection`, `Query`, `RetrievedCandidate`, `RetrievedCandidateCollection`, `Context`, `Prompt`, `GeneratedAnswer`, `Image`, `Audio`, `Video`, `VideoFrame`, `TemporalSegment`, `Table`, `Metadata`, `NumericScore`, `EvaluationResult`.

Each payload supports (as applicable): unique id, source/document/parent ids, original content or **artifact ref**, metadata, source reference, page/timestamp/offsets, provenance, transformation history, algorithm+version info. Collections are typed containers preserving element lineage. Nodes append information (scores/ranks/annotations) without destroying prior content.

### 3.3 Algorithm/provider interfaces (strategy seams)
General interfaces (inputs/outputs/config/validation/behavior): `DocumentParser`, `DocumentProcessor`, `ChunkingStrategy`, `EmbeddingProvider`, `VectorStore`, `Retriever`, `CandidateSelector` (not Top-K-only), `Reranker`, `ContextBuilder`, `LLMProvider`, `OutputValidator`, `EvaluationMetric`.
- Implementations are replaceable adapters (e.g. Recursive/Semantic chunkers, BM25/Hybrid retrievers, TopK/MMR/reward/adaptive selectors, Ollama/OpenAI/Anthropic/Gemini/HF/custom providers, Qdrant/Chroma/FAISS/Milvus stores) registered by id+version.
- Provider configs are persisted and selectable via UI; secrets stored encrypted/server-side and never returned to frontend. No provider logic inside DAG engine.

### 3.4 DAG engine (independent)
- Graph definition with typed ports, compatibility validation, DAG/cycle rules (explicit bounded control-flow constructs only), topological sort, dependency resolution, parallel branches, scheduling, retries/timeouts/cancellation, error propagation, caching, artifact management, execution state.
- Two linked graph kinds: **Ingestion/Indexing** and **Query/Retrieval/Generation** (share contracts, may reference produced indexes/artifacts).
- Streaming-capable node/runtime contracts where supported; avoid loading whole datasets into RAM (artifact refs, chunked/iterative IO).

### 3.5 Execution, events, artifacts, observability
- Execution entities carry: execution id, pipeline id+version snapshot, node id+version, state, start/end/duration, input/output **refs**, params, errors/warnings, metrics, logs, artifact refs.
- Structured events: `ExecutionStarted|NodeQueued|NodeStarted|NodeProgress|NodeCompleted|NodeFailed|NodeSkipped|ExecutionCompleted|ExecutionFailed|ExecutionCancelled` with ids/timestamps/payload for UI.
- SSE/WS stream for canvas/monitor/logs/metrics; OpenTelemetry traces/metrics/log correlation. Artifact store (MinIO/local) for chunks, embeddings, candidates, scores, prompts, answers, large files — never bulk blobs in execution tables.

### 3.6 Persistence (domain-aligned, repositories)
Entities/repositories: `Users`, `Projects`, `Pipelines`, `PipelineVersions`, `Nodes` (instances), `NodeDefinitions`, `NodeVersions`, `Connections`, `DataSources`, `Datasets`, `Models`, `ProviderConfigurations`, `Executions`, `NodeExecutions`, `ExecutionEvents`, `Artifacts`, `Experiments`, `EvaluationResults`, `CustomComponents`.
- Immutable execution snapshots (pipeline/config/versions) for reproducibility.
- SQLAlchemy 2 models + Alembic migrations in `infrastructure/database`; repository interfaces in domain/application.

### 3.7 Custom Python nodes (secure, pluggable)
- Standard implementation contract + registry metadata; typed IO/params/deps/tests/versioning/import-export; indistinguishable from built-ins to engine.
- **Never executed in FastAPI process**: isolated worker runtime with CPU/memory/time/permission limits, dependency management, and artifact/log/result capture.

## 4. Backend module layout (target)
```
backend/
  app/
    main.py
    core/            # config, logging, security/secrets, DI, exceptions
    domain/          # nodes, pipelines, execution, artifacts, datasets, providers, evaluation (+ value objects/contracts)
    application/     # use cases per bounded area (projects, pipelines, executions, nodes, experiments, evaluations, datasets, models)
    infrastructure/  # database, repositories, storage, queue, providers, monitoring, security impl
    api/v1/          # routers, schemas, dependencies (frontend-compatible)
    engine/          # graph, validation, scheduler, runtime, events, caching
    registry/        # node_registry, provider_registry
    components/      # builtin/, custom/ (reference implementations & user artifacts)
    workers/         # celery_app, tasks
  tests/{unit,integration,contracts,execution}/
  alembic/
  docker/
  pyproject.toml Dockerfile docker-compose.yml .env.example
```

## 5. Phased implementation plan & validation gates
- **Phase 1 (this step)**: frontend analysis, architecture, API/contracts mapping. *Gate*: docs reviewed against frontend code/types/mocks.
- **Phase 2**: config, DB/session/migrations baseline, domain entities/contracts, Pydantic schemas, repository interfaces, DI, base API app, node registry + port/param system. *Gate*: app boots, OpenAPI exposes base routes, schema/contract unit tests pass.
- **Phase 3**: graph representation/validation/typed compatibility, execution planning, runtime interfaces, execution state, event model. *Gate*: validate/sample plan tests.
- **Phase 4**: persistence + CRUD/versioning, execution/artifact storage, frontend-compatible APIs. *Gate*: integration/contract tests vs frontend schemas.
- **Phase 5**: Celery workers, scheduling, SSE real-time, logs/metrics/artifact inspection. *Gate*: end-to-end run streaming observable.
- **Phase 6**: builtin reference nodes, provider/store adapters (Ollama + interfaces), custom Python isolated runtime. *Gate*: plugin registration/execution contract tests.

No phase advances without tests/validation for the previous phase.

## 6. Key architectural decisions (initial)
- **Modular monolith now**: single deployable API + separate worker processes; avoid premature microservices.
- **Pydantic v2 as contract backbone** for API/domain DTOs and node/data schemas; controlled extension fields (`extra`/metadata) instead of untyped blobs.
- **Artifacts over blobs-in-DB**: MinIO/S3-compatible storage for large/intermediate data; DB stores references, hashes, metadata, lineage.
- **Immutable run snapshots**: execution records freeze pipeline/version/config/provider refs for reproducibility.
- **Secrets safety**: provider credentials encrypted at rest, referenced by id; API responses redact secrets.
- **Compatibility-first API**: routes/shapes aligned to existing frontend modules/types/mock behavior; OpenAPI -> TypeScript generation planned to prevent drift.
- **Reference implementations + contract tests** per interface to guarantee substitutability.

## 7. Immediate next deliverables (Phase 2 start)
- Backend project scaffolding (`pyproject.toml`, Docker/Compose, `.env.example`, Alembic bootstrap, app factory, settings, DB base/session).
- Domain contract modules for node specs/ports/params/results and typed data/lineage primitives.
- API v1 router/schemas skeleton matching frontend endpoints (initial compatible responses/persistence stubs where needed).
- Initial unit/contract tests and run instructions.

## 8. Implemented increment — real in-process execution (2026-11-21)
The execution path is no longer a UI simulation. `/api/v1/executions/:id/stream` now runs the DAG through registered node implementations:

- `engine/executor.py`: `PipelineExecutor` resolves specs/implementations, binds typed edge inputs, executes plan levels, captures `NodeResult`, artifacts, metrics, failures, skips, and cancellation. It also applies `TimeoutPolicy` (node/execution) and `RetryPolicy` with backoff and retry log events.
- `engine/context.py`: concrete `NodeRuntimeContext` (artifacts, secrets, providers, live cancellation token, logs/events).
- `engine/serialization.py`: lossless JSON conversion for Pydantic/enums/datetimes.
- `components/builtin/reference_nodes.py`: deterministic reference nodes for source, chunking, embeddings, vector store, query input, hybrid retrieval, reranking, and extractive generation; they cooperate with cancellation during their loops.
- `application/result_builder.py`: builds the frontend `ExecutionResult` from real node outputs (query, documents, lineage, node summaries, embedding inspector, runtime breakdown).
- `application/execution_stream.py`: SSE now reflects real node execution and persists artifacts/results through the persistence bridge.
- `application/execution_persistence.py`: in `database` mode, `ExecutionResult` snapshots and artifact refs are read from/written to SQL tables (`execution_results`, `artifacts`), with in-memory mirrors for fallback.
- `application/pipeline_persistence.py`: in `database` mode, `/pipelines` list/get/create/update/delete/duplicate use the SQL pipeline repository as source-of-truth. The full API `Pipeline` round-trips losslessly in `PipelineSpec.metadata["api_snapshot"]`; demo fixtures are seeded automatically and memory state is mirrored for fallback.
- `application/node_execution_persistence.py`: per-node status, timing, metrics, warnings and output artifact refs are written to `node_executions` via the execution repository and projected by `GET /executions/:id/nodes`; seeded runs fall back to the API snapshot. JSON payloads are normalized before SQL writes.
- `execution_runtime.default_timeout_policy/default_retry_policy` read settings (`execution_node_timeout_seconds`, `execution_default_timeout_seconds`, `execution_retry_max_attempts`, `execution_retry_backoff_seconds`); `execution_stream._node_policies` applies per-node overrides from `PipelineNode.config`.
- `engine/executor.py`: independent nodes in the same plan level run concurrently behind an `asyncio.Semaphore` sized by `execution_max_parallel_nodes`; events are emitted grouped by node in plan order. `NodePolicies` carries per-node timeout/retry overrides.
- `domain/interfaces/services.py` + `infrastructure/coordination.py`: `StreamCoordinator` gives one owner per execution. `InMemoryStreamCoordinator` (default) uses asyncio events/locks; `RedisStreamCoordinator` uses a `SET NX EX` lock with compare-and-delete release and pub/sub plus a done key so late subscribers never miss completion. `ExecutionLimiter` caps concurrent runs: `InMemoryExecutionLimiter` wraps a semaphore, `RedisExecutionLimiter` uses a TTL-scored sorted set and purges stale slots from crashed workers. `core/bootstrap.py` wires both into `AppContainer`; `application/execution_stream.py` uses them instead of a per-process dict, reloading the API snapshot before replaying the terminal frame and emitting `status: queued` while waiting for a slot.
- `POST /pipelines/:id/run` accepts an optional `{query, inputs}` body; the frontend can still call it with no body.
- Artifact retrieval returns real artifact URLs, content, and a listing endpoint `/executions/:id/artifacts`. `infrastructure/storage/filesystem_store.py` adds a durable local backend (`ARTIFACT_STORE_BACKEND=filesystem`) with SHA256 checksums, relative object refs and retention cleanup; API payloads expose only HTTP(S) URLs from object stores, otherwise the `/content` proxy path.

Remaining gaps are intentionally deferred: external provider adapters, Celery/worker execution, durable artifact content (MinIO) and retention/cleanup, isolated custom-node runtime, and evaluation/experiment execution. See `ROADMAP.md`.
