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
# copia .env.example in .env per configurare provider e token API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: `http://localhost:8000/docs` (OpenAPI). Health: `GET /api/v1/system/status`.

**Sicurezza:** prima di esporre la API fuori da loopback imposta `API_ACCESS_TOKEN` in `.env`: i metodi mutanti richiedono allora l'header `X-API-Token`. `GET`, `/health`, `/docs` e `/openapi.json` restano accessibili. `app_debug` è `false` di default. Con `APP_ENV=production` l'avvio **fallisce** se `API_ACCESS_TOKEN` o `DATASET_ALLOWED_ROOTS` non sono configurati, e gli errori di inizializzazione dell'infrastruttura o di persistenza vengono propagati invece di degradare silenziosamente a `memory`. Imposta `PROVIDER_SETTINGS_KEY` per cifrare `provider_settings.json` con Fernet; senza chiave il file resta in chiaro e viene emesso un warning all'avvio (la chiave non viene mai loggata).

## Provider reali

`pl_real_rag` usa provider reali selezionati per capability: Hugging Face (`sentence-transformers`, `transformers`, modelli configurabili con `HF_EMBEDDING_MODEL`, `HF_RERANKER_MODEL`, `HF_GENERATOR_MODEL`), Ollama (`ollama serve`, `ollama pull nomic-embed-text`, `ollama pull llama3.2:1b`, `OLLAMA_BASE_URL`) e OpenAI (`OPENAI_API_KEY`, `OPENAI_BASE_URL`). La configurazione può essere inviata anche a `PATCH /api/v1/providers/settings`; la chiave grezza non torna mai nelle risposte. Il frontend deve usare `VITE_USE_MOCKS=false`. Lo stato dei provider è in `GET /api/v1/providers/status`.

## Esecuzione reale in-process (reference + provider reali)
- `POST /api/v1/pipelines/:id/run` creates an execution; `GET /api/v1/executions/:id/stream` (SSE) executes the DAG through registered node implementations.
- Body opzionale per il run: `{"query": "..."}` oppure `{"inputs": {"node_id": {"port": value}}}`.
- Nodi inclusi: document source, semantic chunking, embeddings deterministici, vector index in-memory, query input, hybrid retrieval, reranker lessicale, generazione estrattiva. `pl_real_rag` sostituisce embedding/reranking/generazione con i provider reali di cui sopra, senza fallback silenzioso.
- I risultati sono reali e ispezionabili via `GET /api/v1/executions/:id/results`; gli output dei nodi sono salvati come artifact e recuperabili via `GET /api/v1/executions/:id/artifacts` e `GET /api/v1/executions/:id/artifacts/:artifactId` (+ `/content`).
- Il dettaglio per nodo (status, durata, metriche, output refs) è disponibile via `GET /api/v1/executions/:id/nodes` ed è persistito su `node_executions` in modalità `database`.
- L'executor applica `TimeoutPolicy`/`RetryPolicy` e passa un token di cancellazione live ai nodi; i nodi reference cooperano alla cancellazione durante i loro loop. Default via env (`EXECUTION_NODE_TIMEOUT_SECONDS`, `EXECUTION_RETRY_MAX_ATTEMPTS`, `EXECUTION_RETRY_BACKOFF_SECONDS`) e override per-nodo in `PipelineNode.config` (`timeoutSeconds`, `retryMaxAttempts`, `retryBackoffSeconds`).
- I nodi indipendenti di uno stesso livello girano in parallelo con semaforo `EXECUTION_MAX_PARALLEL_NODES` (default 4).
- Lo stream SSE è idempotente: un solo client esegue il run, gli altri attendono e riproducono lo stato finale. Con `STREAM_COORDINATION_BACKEND=redis` lock e slot sono distribuiti tra worker (`STREAM_LOCK_TTL_SECONDS`, `STREAM_WAIT_TIMEOUT_SECONDS`, `EXECUTION_MAX_PARALLEL_EXECUTIONS`, `EXECUTION_SLOT_TTL_SECONDS`); il default `memory` copre il singolo processo.
- `EXECUTION_MAX_PARALLEL_EXECUTIONS` limita i run simultanei: chi eccede il limite riceve `status: queued` e parte quando si libera uno slot.
- Il contenuto degli artifact può essere durevole con `ARTIFACT_STORE_BACKEND=filesystem` (`ARTIFACT_ROOT_DIR`, `ARTIFACT_RETENTION_DAYS`): file su disco, checksum SHA256, ref relativi e pulizia automatica dei file scaduti. In alternativa è disponibile `minio`; il default resta `memory` per sviluppo.
- Limite attuale: runtime in-process e worker Celery da completare; Qdrant non è attivo (l'indice resta in-memory). In modalità `database` pipeline, esecuzioni, node executions, risultati e artifact refs sono persistenti. Vedi `ROADMAP.md`.

## Dataset e corpus di dati

I dataset creati dalla UI sono salvati in `data/datasets.json` (accanto a `data/documents.json`, configurabile con `RAG_DATASET_PATH`). Ogni dataset ha connettore (`Local files`, `S3`, `Notion`, `Google Drive`, `Web crawl`, `PostgreSQL`, `REST API`), percorso/URL, dettagli di connessione e l'inventario `files: DatasetFile[]` (`id`, `name`, `path`, `fileType`, `size`, `indexed`). Il testo non è copiato nel JSON: solo i dataset inline legacy conservano `items` con `content`.

- `app/infrastructure/dataset_store.py`: CRUD e sincronizzazione dei dataset su file JSON, senza DB. Sync popola solo `files` (scansione metadati); per `Local files` l'inventario include anche i file non parseabili con `indexed: false`, e `chunks` resta 0.
- `app/components/dataset_connectors.py`: `scan_files` elenca i file di `Local files` e S3 senza leggerne il contenuto; `fetch_documents` estrae da file/URL locali, HTTP (anche per Notion/Drive/web), S3 (minio) e PostgreSQL (SQLAlchemy) quando la pipeline lo richiede. Per i PDF usa `pymupdf` (testo, tabelle, immagini e grafici) con `pypdf` come fallback testuale. Nessuna esecuzione di codice; limite di 200 documenti. I PDF scansionati senza testo danno un errore chiaro (OCR non implementato). `load_documents_for_dataset` (`app/components/corpus.py`) usa i documenti memorizzati solo per i dataset inline legacy, altrimenti legge il connettore a runtime.
- `app/components/corpus.py` + `app/components/algorithms.py`: filtri stdlib `fileTypes`/`fileName` condivisi tra nodo, confronto ed export; `load_documents_for_dataset` risolve il dataset (per id o nome) e applica i filtri.
- `GET /api/v1/datasets/options`: elenco leggero per i selettori; `GET /api/v1/nodes` aggiorna dinamicamente le opzioni del parametro `dataset`. `GET /api/v1/datasets` restituisce anteprime di 240 caratteri e l'inventario; `GET /api/v1/datasets/:id` restituisce il testo integrale dei dataset inline. Tutti gli endpoint che restituiscono `Dataset` (list, get, create, patch, import, sync) redattano `connection` con `***` per le chiavi sensibili; `POST /datasets/sync` sincronizza tutti i dataset e riporta `synced`/`failed`/`syncedAt`. I percorsi locali sono limitati a `DATASET_ALLOWED_ROOTS` e i file `provider_settings.json`/`.env*` non sono mai ingestibili.
- Nodi: `document-source` filtra con `fileTypes` (`all`, `pdf`, `text`, `txt`, `md`, `json`, `jsonl`, `csv`, `documents`, `other`) e `fileName` (sottostringa/wildcard); `merge-documents` ricompone due rami dalle porte `in_documents_a`/`in_documents_b`. L'engine supporta fan-out/fan-in, quindi più sorgenti filtrate alimentano rami diversi prima di un merge.
- `data/documents.json` resta il corpus predefinito quando il nodo non seleziona un dataset; se manca si usa `DEFAULT_CORPUS`.
- Le credenziali di connessione restano nel file JSON locale (single-user) e non vengono mai restituite dalle API. Con `PROVIDER_SETTINGS_KEY` il file `provider_settings.json` viene letto/scritto cifrato (Fernet) con migrazione automatica da file in chiaro; senza chiave resta in chiaro con un warning. Non usare segreti reali in ambienti condivisi; usa `API_ACCESS_TOKEN` prima di esporre la API.

### Estrazione componenti dai PDF

- Il nodo `document-component-extraction` (categoria *Document Processing*) estrae testo, tabelle in Markdown, immagini incorporate e grafici vettoriali con didascalie/etichette. Le immagini vengono salvate come artifact; `out_documents` contiene il testo arricchito dalle sezioni `## Tabelle` e `## Immagini e grafici`, mentre `out_components` espone i componenti strutturati senza dati raw.
- Parametri: `extractTables`, `extractImages`, `extractFigures`, `mergeIntoText` e `descriptionMode` (`reference` deterministico di default, `openai`/`ollama` per descrizioni con un modello visione reale, `off` per disattivarle). `visionModel` vuoto usa `OPENAI_VISION_MODEL` o `OLLAMA_VISION_MODEL` (default rispettivamente `gpt-4o-mini` e `llava`).
- Le modalità `openai`/`ollama` usano le impostazioni provider esistenti: serve `OPENAI_API_KEY`/`openai_api_key` oppure un runtime Ollama raggiungibile con un modello visione. La modalità `reference` non chiama alcun modello: costruisce la descrizione da didascalie, etichette e geometria.
- Il testo arricchito entra nel chunking come qualsiasi altro documento. I metadati compatti (`componentCounts`, `enrichment`, `hasVisuals`, `visualRefs`) seguono chunk → embedding → indice → candidati di retrieval, mentre i dati binari grezzi restano fuori dall'indice.

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
- `GET /api/v1/pipelines/:id/export?format=python&query=...` scarica uno script **dual-mode**: per pipeline deterministiche è standalone (solo stdlib); per `pl_real_rag` include `PROVIDER_CONFIG` e importa il layer provider del backend (nessuna chiave incorporata). La config viene letta dal grafo della pipeline; lo script si esegue con `python pipeline.py "domanda"` o `python pipeline.py "domanda" --json`. Non serve sandbox perché il codice è generato da template, non caricato dall'utente.
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
