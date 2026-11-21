# RAG STUDIO API Contracts (Frontend Compatibility)

Base URL: `/api/v1` (configurable via `VITE_API_URL`). JSON request/response. Errors: non-2xx with body containing `detail` (string/object) as used by `frontend/src/api/client.ts` (`ApiError`).

> Source of truth for compatibility: `frontend/src/api/*.api.ts`, `frontend/src/types/index.ts`, and `frontend/src/api/mock/adapter.ts` behavior. Backend must match these shapes/paths or provide an explicit, frontend-updated migration (prefer matching).

## 1. System / workspace / discovery
| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| GET | `/system/status` | — | `SystemStatus` `{state,version,python,connected,branch,errors,warnings}` | Health/diagnostics badge |
| GET | `/workspace` | — | `Workspace` `{id,name,plan,role}` | Current workspace |
| GET | `/dashboard` | — | `DashboardData` `{metrics,projects,pipelines,activity}` | Aggregate view |
| GET | `/activity` | — | `ActivityItem[]` | Recent activity |
| GET | `/search?q=` | query `q` | `SearchResult[]` `{id,type,title,subtitle,href}` | Global search |

## 2. Projects
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/projects` | — | `Project[]` |
| GET | `/projects/:id` | — | `Project` |
| POST | `/projects` | `{name, description?}` | `Project` |
| PATCH | `/projects/:id` | `Partial<Project>` | `Project` |
| DELETE | `/projects/:id` | — | `{ok:boolean}` or 204 |

`Project`: `{id,name,description,health,pipelineCount,chunkCount,editedAt,updatedAt,accent,market?}`.

## 3. Pipelines & graph
| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| GET | `/pipelines` | — | `PipelineSummary[]` | List view |
| GET | `/pipelines/:id` | — | `Pipeline` (full graph) | Editor load |
| POST | `/pipelines` | `{name, projectId?, template?: 'blank'|'starter'}` | `Pipeline` | Create |
| PATCH | `/pipelines/:id` | `Partial<Pipeline>` (nodes/edges/config/name/status/env/...) | `Pipeline` | Save/update graph |
| DELETE | `/pipelines/:id` | — | `{ok:boolean}` |  |
| POST | `/pipelines/:id/validate` | — | `ValidationResult` `{valid,errors[],warnings[],checkedAt}` | Typed/graph validation |
| POST | `/pipelines/:id/run` | `{query?, inputs?}` (optional) | `Execution` (queued/running) | Start run; body optional, `query` overrides input nodes |
| POST | `/pipelines/:id/duplicate` | — | `Pipeline` |  |
| GET | `/pipelines/:id/export` | query `format=json\|python`, `query?` | `Pipeline` (json) oppure `text/x-python` | Con `format=python` restituisce uno script standalone con header `Content-Disposition: attachment`; `query` imposta la query di default dello script |

Key types:
- `Pipeline`: `{id,projectId,name,description,environment('Development'|'Staging'|'Production'),status('draft'|'valid'|'running'|'failed'),version,updatedAt,nodes:PipelineNode[],edges:PipelineEdge[],lastRun?}`
- `PipelineNode`: `{id,definitionId,name,category,kind,accent,position{x,y},config{[k]:string|number|boolean},inputs:PortDefinition[],outputs:PortDefinition[],status?,durationMs?}`
  - Runtime policy keys in `config`: `timeoutSeconds`, `retryMaxAttempts`, `retryBackoffSeconds` (override settings defaults for that node).
- `PipelineEdge`: `{id,source,target,sourceHandle?,targetHandle?,dataType?}`
- `PipelineSummary`: `{id,projectId,projectName,name,nodeCount,connectionCount,status,environment,updatedAt,lastRunStatus?,lastRunAt?}`
- `ValidationIssue`: `{id,severity('error'|'warning'),message,nodeId?}`

**Backend responsibility:** persist versioned definitions/snapshots; validation must include port/type compatibility and graph rules; run must create immutable execution snapshot.

## 4. Node registry / catalog
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/nodes` | — | `NodeDefinition[]` |
| GET | `/nodes/catalog` | — | `NodeCatalogCategory[]` `{category,description,nodes[]}` |

`NodeDefinition`: `{id,name,category,kind,description,summary?,documentation?,accent,inputs:PortDefinition[],outputs:PortDefinition[],params:ParamDefinition[],tags[],custom?,version?}`. Definitions drive UI inspectors/forms; must be derived from registry/spec contracts (not hardcoded per-algorithm in core).

Nodi per le pipeline ibride:
- `document-source`: parametri `dataset` (opzioni dinamiche da `/datasets/options`), `fileTypes` (`all`, `pdf`, `text`, `txt`, `md`, `json`, `jsonl`, `csv`, `documents`, `other`), `fileName` (sottostringa o wildcard `*`); usa `load_documents_for_dataset(dataset, fileTypes, fileName)`.
- `merge-documents`: due input `in_documents_a`/`in_documents_b` e un output `documents`; unisce e deduplica per id. Il grafo supporta fan-out/fan-in, quindi più sorgenti filtrate possono alimentare rami diversi prima del merge.

## 5. Executions, monitoring, results, artifacts (real-time)
| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| GET | `/executions` | — | `Execution[]` | History/list |
| GET | `/executions/:id` | — | `Execution` | Detail/polling |
| POST | `/executions` | — | `Execution` | (supported by mock) start/ad-hoc |
| POST | `/executions/:id/stop` | — | `{ok:boolean,status:string}` | Cancel/stop |
| GET | `/executions/:id/logs` | — | `LogEntry[]` |  |
| GET | `/executions/:id/nodes` | — | `NodeExecutionRecord[]` | Persisted per-node status/timing/output refs; falls back to `Execution.nodeRuns` for seeded runs |
| GET | `/executions/:id/events` | — | `ExecutionEvent[]` | Persisted domain events |
| GET | `/executions/:id/results` | — | `ExecutionResult` | Intermediate/final inspectable results; DB source-of-truth in `database` mode |
| GET | `/executions/:id/artifacts` | — | `ArtifactSummary[]` | Lists artifact refs for the execution |
| GET | `/executions/:id/artifacts/:artifactId` | — | `{id,name?,kind?,contentType?,sizeBytes?,url}` | Artifact retrieval |
| GET | `/executions/:id/artifacts/:artifactId/content` | — | artifact bytes/JSON | Artifact content (memory/dev) |
| GET (SSE) | `/executions/:id/stream` | — | `text/event-stream` | Real-time progress (**frontend uses EventSource**); only one connection executes the run, others replay the final state |

`ArtifactSummary`: `{id,name?,kind?,contentType?,sizeBytes?,url}`; `url` is a proxy path under `/api/v1` or an HTTP(S) object-store URL when configured. Filesystem-backed artifacts always use the proxy path (local `file://` URIs are never returned to clients).

`Execution`: `{id,runNumber,pipelineId,pipelineName,status,startedAt,finishedAt?,durationMs,tokens,cost,environment,trigger,traceId,nodeRuns:NodeRun[],logs:LogEntry[],stagesCached?,errors,warnings}`.
- `NodeRun`: `{nodeId,name,kind,status('pending'|'running'|'completed'|'failed'|'skipped'),durationMs,outputCount,accent,startedAt?}`
- `NodeExecutionRecord`: `{id,executionId,nodeId,nodeDefinitionId?,status,attempt,startedAt?,finishedAt?,durationMs?,outputRefs,metrics,warnings,error?,cached}`; `outputRefs` maps output names to artifact refs (e.g. `{outputs:{artifactId,...}}`).
- `LogEntry`: `{id,timestamp,level('INFO'|'WARN'|'ERROR'|'DONE'|'DEBUG'),message,node?}`

**SSE event payload** (`data: JSON`): `ExecutionStreamEvent {type:'status'|'node'|'log'|'done'|'error', status?, node?, log?, execution?}`.

Stream idempotence: the first client to connect acquires ownership via `StreamCoordinator` (`memory` or `redis` backend). Concurrent/reconnecting clients get a `status` frame, wait for the completion signal, then replay the persisted terminal `done`/`error` frame without launching a second run. If the wait exceeds `STREAM_WAIT_TIMEOUT_SECONDS` and the lock is still held, the client receives a WARN log and can reconnect; if the lock expired, the waiting client takes over. When `EXECUTION_MAX_PARALLEL_EXECUTIONS` slots are all busy, the owning client receives `status: queued` before execution starts.

`ExecutionResult`: `{id,executionId,query,retrievedCount,selectedCount,errorCount,stages[],traceId,documents:RetrievedDocument[],chunk,lineage[],nodeOutputs[],generatedAnswer,answerMeta,embedding:EmbeddingInspector,runtime{latencyMs,peakMemoryMb,tokensPerSecond,breakdown[]}}`.
- Large/intermediate data (documents/chunks/embeddings/candidates/prompts/answers) must be artifact-backed; API may inline small views but persist references.

## 6. Datasets, data sources, ingestion jobs
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/datasets` | — | `DatasetsData` `{metrics,datasets,sources,jobs,connectors}`; gli `items` hanno `content` troncato a 240 caratteri, `files` è completo |
| GET | `/datasets/metrics` | — | `DatasetMetrics` |
| GET | `/datasets/connectors` | — | `{connectors: string[]}` |
| GET | `/datasets/options` | — | `{value,label,description}[]` per il selettore del nodo |
| POST | `/datasets` | `{name,sourceType,path?,format?,items?,connection?}` | `Dataset` (201) |
| GET | `/datasets/:id` | — | `Dataset` |
| PATCH | `/datasets/:id` | `Partial<Dataset>` | `Dataset` |
| DELETE | `/datasets/:id` | — | 204 |
| POST | `/datasets/:id/documents` | `{filename,text}` | `Dataset` con i nuovi documenti |
| POST | `/datasets/:id/sync` | — | `Dataset` con l'inventario `files` aggiornato e `items: []` per i dataset con connettore |
| POST | `/datasets/sync` | — | `{ok,syncedAt}` (sync all) |
| POST | `/datasets/:id/reindex` | — | `{ok,datasetId,jobId}` |
| GET | `/datasources` | — | `DataSource[]` |
| POST | `/datasources` | `{name,type}` | `DataSource` |
| POST | `/datasources/:id/sync` | — | `{ok,syncedAt}` |
| GET | `/ingestion-jobs` | — | `IngestionJob[]` |

Types: `Dataset`, `DatasetMetrics`, `DataSource`, `IngestionJob`, `DatasetsData` as in frontend. `Dataset` include `items: DatasetDocument[]` (`id`, `title`, `source`, `content`, `fileType?`) e `files: DatasetFile[]` (`id`, `name`, `path`, `fileType`, `size`, `indexed`), oltre a `connection: Record<string, unknown>`. `POST /datasets/:id/sync` aggiorna solo `files`: l'inventario elenca tutti i file trovati (per `Local files` e `S3` senza scaricarli; per `Local files` anche quelli non parseabili, con `indexed: false`) e non estrae testo, quindi `items` resta vuoto per i dataset con connettore. `chunks` è mantenuto per compatibilità ma impostato a `0`: il chunking avviene solo nel nodo *Semantic chunking* della pipeline, con la dimensione scelta lì. I dataset sono persistiti in `backend/data/datasets.json` senza copie del testo. Il nodo *Document source*, `/comparison/run` e l'export Python leggono i documenti dal connettore a runtime tramite `load_documents_for_dataset`; `items` resta usato solo per i dataset inline legacy. La creazione via UI non accetta più testo incollato né file caricati: i file vanno spostati nella cartella/endpoint del connettore prima di sincronizzare. I connettori supportati sono `Local files`, `S3`, `Notion`, `Google Drive`, `Web crawl`, `PostgreSQL`, `REST API`; per Notion/Drive/web si usa il client HTTP generico con header configurabili.

## 7. Models & providers
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/models` | — | `ModelsData` `{providers,models,resources}` |
| GET | `/models/providers` | — | `Provider[]` |
| GET | `/models/resources` | — | `ModelResources` |
| POST | `/models` | `{name,provider,type}` | `Model` (register) |
| PATCH | `/models/:id` | `Partial<Model>` | `Model` |
| POST | `/models/:id/test` | `{prompt}` | `ModelTestResponse` `{modelId,output,latencyMs,tokens,cost}` |

Provider configs/credentials endpoints to be added compatibly for settings UI (secrets never returned).

## 8. Evaluations
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/evaluations` | — | `EvaluationData` `{metrics,trend,comparison,questions,meta,runs,settings}` |
| POST | `/evaluations/run` | `{pipeline,dataset,sampleSize}` | `{id,status,startedAt}` |
| PATCH | `/evaluations/settings` | `Partial<settings>` | updated settings |

## 9. Experiments
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/experiments` | — | `ExperimentData` `{project,summary,experiments,comparison}` |
| POST | `/experiments` | `{name}` | `Experiment` |
| POST | `/experiments/compare` | `{ids:string[]}` | `ComparisonData` |
| POST | `/experiments/:id/promote` | — | `{ok,experimentId}` |

## 10. Confronto algoritmico ed export Python

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/comparison/run` | `{query: string, variants: ComparisonVariant[], datasetId?: string}` | `ComparisonResponse` |

- `datasetId` (opzionale) seleziona il dataset usato da tutte le varianti; se assente si usa `backend/data/documents.json`.
- `ComparisonVariant`: `{id: string, label: string, pipelineId?: string, config?: Record<string, string|number|boolean>}`. Con `pipelineId` la config parte dal grafo della pipeline; `config` sovrascrive i valori. Senza `pipelineId` si usano i default.
- `ComparisonResponse`: `{query, variants: VariantResult[]}`; `VariantResult`: `{id, label, config, answer, citations, documents, metrics, durationMs}`.
- `documents`: `{rank, title, source, chunkId, score, excerpt}` (top 5 selezionati); `metrics`: `{documents, chunks, dimensions, retrieved, selected, tokens}`.
- La UI usa tre preset: `Hybrid + extractive`, `BM25 + concise`, `Dense + diversity`. In mock mode l'adapter restituisce risultati seedati e l'export `.py` è un segnaposto che chiede di impostare `VITE_USE_MOCKS=false`.

Chiavi di configurazione algoritmiche (lettere maiuscole/minuscole come sotto, lette da `PipelineNode.config`):

| Chiave | Valori | Effetto |
|---|---|---|
| `chunkStrategy` | `fixed` \| `recursive` \| `sentence` | Confini dei chunk |
| `retrievalAlgorithm` | `hybrid` \| `dense` \| `bm25` \| `rrf` | Metodo di ranking |
| `alpha` | `0..1` | Peso dense in `hybrid` |
| `rerankStrategy` | `lexical` \| `diversity` \| `none` | Ordinamento finale |
| `generationStrategy` | `extractive` \| `first` \| `concise` | Costruzione della risposta |
| `maxSentences` | intero | Numero massimo di frasi |

Lo script exportato è generato da template, include le funzioni pure di `app/components/algorithms.py`, `PIPELINE_CONFIG`, `DOCUMENTS` (i documenti del dataset selezionato nel nodo *Document source*) e `main()`; si esegue con `python pipeline.py "domanda"` oppure `python pipeline.py "domanda" --json`. Non richiede dipendenze esterne.

| Chiave | Valori | Effetto |
|---|---|---|
| `dataset` | id o nome di un dataset di progetto | Sorgente documenti per nodo, confronto ed export |
| `fileTypes` | `all` \| `pdf` \| `text` \| `txt` \| `md` \| `json` \| `jsonl` \| `csv` \| `documents` \| `other` | Filtra i documenti in ingresso al nodo *Document source* |
| `fileName` | sottostringa o wildcard `*` | Filtra per titolo/percorso nel nodo *Document source* |

Le chiavi di filtro sono lette anche da `/comparison/run` e dallo script exportato: `PIPELINE_CONFIG` contiene `file_types`/`file_name` e `run_pipeline` applica `filter_documents` agli stessi documenti.

## 11. Custom nodes
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/custom-nodes` | — | `CustomNode[]` (used by mock/registry views) |
| GET | `/custom-nodes/templates` | — | `{id,name,description}[]` |
| GET | `/custom-nodes/:id` | — | `CustomNode` |
| PATCH | `/custom-nodes/:id` | `Partial<CustomNode>` | `CustomNode` |
| POST | `/custom-nodes/:id/test` | — | `CustomNodeTestOutput` |
| POST | `/custom-nodes/:id/tests` | — | `TestRun` |
| GET | `/custom-nodes/:id/test-results` | — | `TestRun` |
| POST | `/custom-nodes/:id/dependencies` | `{name,version}` | `CustomNodeDependency` |
| POST | `/custom-nodes/:id/publish` | — | `{id,version,status}` |
| GET | `/custom-nodes/:id/versions` | — | `CustomNodeVersion[]` |
| POST | `/custom-nodes/:id/versions/:version/restore` | — | `CustomNode` |

`CustomNode` includes files/code, typed params/IO, dependencies, versions metadata. Execution/testing must run in isolated workers.

## 12. Cross-cutting contract rules
- **IDs**: string IDs (opaque) across entities.
- **Immutability**: executions reference immutable pipeline/version/config snapshots.
- **Artifacts**: responses may include inline summaries for UI but must be backed by artifact records/refs for large data.
- **Secrets**: never return API keys/credentials; use provider config ids/status only.
- **Streaming**: SSE for execution progress; payloads stable and typed for frontend consumption.
- **Versioning**: APIs under `/api/v1`; OpenAPI schema must be kept accurate for TypeScript generation.
- **Validation**: server-side validation (Pydantic) for all inputs; graph/port compatibility enforced by engine contracts.

## 13. Known gaps / to align during implementation
- `GET /projects/:id` not consumed by current UI module but is a natural CRUD endpoint (keep available).
- `/nodes` vs catalog/definitions and custom-node listing should converge on registry-backed definitions without duplicating sources of truth.
- Provider configuration CRUD (with secret handling) needed for settings beyond current mock; design compatibly.
- Pagination/filtering not present in all mock endpoints; introduce optional query params without breaking existing clients.
- Export JSON lato client resta disponibile; l'export Python è ora server-side (`GET /pipelines/:id/export?format=python`). Valutare in futuro un export matrix/report server-side.
