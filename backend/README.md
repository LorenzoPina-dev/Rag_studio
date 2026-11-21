# RAG STUDIO Backend

Modular, algorithm-agnostic backend foundation for RAG STUDIO (FastAPI + Pydantic v2 + SQLAlchemy 2 + PostgreSQL/Redis/MinIO/Celery).

## Documentazione di fase
- `ARCHITECTURE.md` — analisi frontend, contratti dominio/engine, architettura a layer, piano incrementale.
- `API_CONTRACTS.md` — mapping contratti `/api/v1` compatibili col frontend.
- `../DECISIONS.md` — scelta di mantenere l'infrastruttura avanzata come opt-in nel percorso principale.

## Quick start (locale, dev)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e .[dev]
# .env è già presente con i backend "memory" (nessun servizio esterno richiesto)
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs` (OpenAPI). Health: `GET /api/v1/system/status`.

## Esecuzione reale in-process (reference runtime)
- `POST /api/v1/pipelines/:id/run` creates an execution; `GET /api/v1/executions/:id/stream` (SSE) executes the DAG through registered node implementations.
- Body opzionale per il run: `{"query": "..."}` oppure `{"inputs": {"node_id": {"port": value}}}`.
- Nodi reference inclusi: document source, semantic chunking, embeddings deterministici, vector index, query input, hybrid retrieval, reranker lessicale, generazione estrattiva.
- I risultati sono reali e ispezionabili via `GET /api/v1/executions/:id/results`; gli output dei nodi sono salvati come artifact e recuperabili via `GET /api/v1/executions/:id/artifacts` e `GET /api/v1/executions/:id/artifacts/:artifactId` (+ `/content`).
- Il dettaglio per nodo (status, durata, metriche, output refs) è disponibile via `GET /api/v1/executions/:id/nodes` ed è persistito su `node_executions` in modalità `database`.
- L'executor applica `TimeoutPolicy`/`RetryPolicy` e passa un token di cancellazione live ai nodi; i nodi reference cooperano alla cancellazione durante i loro loop. Default via env (`EXECUTION_NODE_TIMEOUT_SECONDS`, `EXECUTION_RETRY_MAX_ATTEMPTS`, `EXECUTION_RETRY_BACKOFF_SECONDS`) e override per-nodo in `PipelineNode.config` (`timeoutSeconds`, `retryMaxAttempts`, `retryBackoffSeconds`).
- I nodi indipendenti di uno stesso livello girano in parallelo con semaforo `EXECUTION_MAX_PARALLEL_NODES` (default 4).
- Lo stream SSE è idempotente: un solo client esegue il run, gli altri attendono e riproducono lo stato finale. Con `STREAM_COORDINATION_BACKEND=redis` lock e slot sono distribuiti tra worker (`STREAM_LOCK_TTL_SECONDS`, `STREAM_WAIT_TIMEOUT_SECONDS`, `EXECUTION_MAX_PARALLEL_EXECUTIONS`, `EXECUTION_SLOT_TTL_SECONDS`); il default `memory` copre il singolo processo.
- `EXECUTION_MAX_PARALLEL_EXECUTIONS` limita i run simultanei: chi eccede il limite riceve `status: queued` e parte quando si libera uno slot.
- Il contenuto degli artifact può essere durevole con `ARTIFACT_STORE_BACKEND=filesystem` (`ARTIFACT_ROOT_DIR`, `ARTIFACT_RETENTION_DAYS`): file su disco, checksum SHA256, ref relativi e pulizia automatica dei file scaduti. In alternativa è disponibile `minio`; il default resta `memory` per sviluppo.
- Limite attuale: runtime in-process, nessun provider esterno e worker Celery da completare. In modalità `database` pipeline, esecuzioni, node executions, risultati e artifact refs sono persistenti. Vedi `ROADMAP.md`.

## Dataset e corpus di dati

I dataset creati dalla UI sono salvati in `data/datasets.json` (accanto a `data/documents.json`, configurabile con `RAG_DATASET_PATH`). Ogni dataset ha connettore (`Local files`, `S3`, `Notion`, `Google Drive`, `Web crawl`, `PostgreSQL`, `REST API`), percorso/URL, dettagli di connessione, i documenti reali (`id`, `title`, `source`, `content`, `fileType`) e l'inventario `files: DatasetFile[]` (`id`, `name`, `path`, `fileType`, `size`, `indexed`).

- `app/infrastructure/dataset_store.py`: CRUD e sincronizzazione dei dataset su file JSON, senza DB. Sync popola solo `files` (scansione metadati); per `Local files` l'inventario include anche i file non parseabili con `indexed: false`, e `chunks` resta 0.
- `app/components/dataset_connectors.py`: `scan_files` elenca i file di `Local files` e S3 senza leggerne il contenuto; `fetch_documents` estrae il testo da file/URL locali, HTTP (anche per Notion/Drive/web), S3 (minio) e PostgreSQL (SQLAlchemy) quando la pipeline lo richiede, con `pypdf` per i PDF. Nessuna esecuzione di codice; limite di 200 documenti. I PDF scansionati senza testo danno un errore chiaro (OCR non implementato). `load_documents_for_dataset` (`app/components/corpus.py`) usa i documenti memorizzati solo per i dataset inline legacy, altrimenti legge il connettore a runtime.
- `app/components/corpus.py` + `app/components/algorithms.py`: filtri stdlib `fileTypes`/`fileName` condivisi tra nodo, confronto ed export; `load_documents_for_dataset` risolve il dataset (per id o nome) e applica i filtri.
- `GET /api/v1/datasets/options`: elenco leggero per i selettori; `GET /api/v1/nodes` aggiorna dinamicamente le opzioni del parametro `dataset`. `GET /api/v1/datasets` restituisce anteprime di 240 caratteri e l'inventario; `GET /api/v1/datasets/:id` restituisce il testo integrale.
- Nodi: `document-source` filtra con `fileTypes` (`all`, `pdf`, `text`, `txt`, `md`, `json`, `jsonl`, `csv`, `documents`, `other`) e `fileName` (sottostringa/wildcard); `merge-documents` ricompone due rami dalle porte `in_documents_a`/`in_documents_b`. L'engine supporta fan-out/fan-in, quindi più sorgenti filtrate alimentano rami diversi prima di un merge.
- `data/documents.json` resta il corpus predefinito quando il nodo non seleziona un dataset; se manca si usa `DEFAULT_CORPUS`.
- Le credenziali di connessione sono salvate in chiaro nel JSON locale: è un prototipo single-user, non usare segreti reali in ambienti condivisi.

## Varianti algoritmiche, confronto ed export Python

Le funzioni in `app/components/algorithms.py` sono pure e usano solo la stdlib: sono richiamate sia dai nodi reference sia dal generatore di codice, quindi runtime ed export non possono divergere.

- Varianti selezionabili dai parametri dei nodi (nessuna dipendenza nuova):
  - chunking: `fixed`, `recursive`, `sentence` (`chunkStrategy`);
  - retrieval: `hybrid`, `dense`, `bm25`, `rrf` (`retrievalAlgorithm`, `alpha`);
  - reranking: `lexical`, `diversity`, `none` (`rerankStrategy`);
  - generazione: `extractive`, `first`, `concise` (`generationStrategy`, `maxSentences`).
- `POST /api/v1/comparison/run` esegue la stessa query su più varianti e restituisce `answer`, `citations`, `documents`, `metrics` e `durationMs` per ciascuna. Esempio:
  ```bash
  curl -X POST http://localhost:8000/api/v1/comparison/run \
    -H 'Content-Type: application/json' \
    -d '{"query":"What is BM25?","variants":[{"id":"a","label":"Hybrid","config":{}},{"id":"b","label":"BM25 concise","config":{"retrievalAlgorithm":"bm25","generationStrategy":"concise"}}]}'
  ```
- `GET /api/v1/pipelines/:id/export?format=python&query=...` scarica uno script standalone. La config viene letta dal grafo della pipeline; lo script si esegue con `python pipeline.py "domanda"` o `python pipeline.py "domanda" --json`. Non serve sandbox perché il codice è generato da template, non caricato dall'utente; la sandbox entrerà in gioco solo con custom node che eseguono codice utente.
- Il percorso principale resta `memory`, single-process: DB/Redis/filesystem/Celery sono opzionali e non richiesti né dal confronto né dall'export. Vedi `../DECISIONS.md`.

## Persistenza e fondazioni scalabili
- **Backend di persistenza configurabile** via `PERSISTENCE_BACKEND`:
  - `memory` (default): store/adapter in-memory compatibili con il frontend, nessuna dipendenza da DB per sviluppo rapido e test attuali.
  - `database`: abilita wiring verso infrastruttura SQLAlchemy 2/Alembic (engine/session factory e repository DB per pipeline/versioni, esecuzioni, eventi, risultati e artifact refs). Pipeline (liste/CRUD), snapshot API, risultati e refs sono la fonte primaria per `/pipelines`, `/results` e `/artifacts`.
- **Modelli DB:** `pipelines`, `pipeline_versions` (snapshot immutabili), `executions`, `node_executions`, `execution_events` (append-only), `execution_results`, `artifacts`.
- **Migrazioni Alembic:** configurate in `alembic.ini` e `alembic/` (`20260401_0001_initial_persistence_foundation.py`, `20261121_0002_execution_results.py`).
  ```bash
  cd backend
  alembic upgrade head
  ```
- **Worker/async foundation:** app Celery in `app/workers/celery_app.py` e task placeholder in `app/workers/tasks.py` (coda/esecuzione reale da completare con runtime e persistenza come source-of-truth).

## Docker (infra + app)
```bash
cd backend
docker compose up --build
```
Servizi previsti: PostgreSQL, Redis, MinIO, backend API, worker Celery.

## Test
```bash
cd backend
pytest -q
```

## Note
- Frontend: `VITE_API_URL=/api/v1`, SSE `GET /api/v1/executions/:id/stream`, mock mode via `VITE_USE_MOCKS`.
- Le fondamenta sono progettate per evolvere verso esecuzione reale (provider/worker isolati), persistenza come source-of-truth, artifact storage (MinIO) e osservabilità (OpenTelemetry) senza rompere i contratti esistenti.
