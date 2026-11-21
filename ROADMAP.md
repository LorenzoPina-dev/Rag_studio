# RAG Studio — Roadmap

Stato aggiornato al 2026-11-21. Il percorso principale è reale in-process: varianti algoritmiche comparabili, pipeline `pl_real_rag` con provider esterni attivi, export Python dual-mode e infrastruttura avanzata (DB, Redis, filesystem, worker) disponibile solo come opzione. La scelta è registrata in `DECISIONS.md`. I prossimi step riguardano coda esecuzioni, vector store sostituibile e runtime isolato.

## Fatto

- Contratti frontend-compatibili `/api/v1` per tutte le superfici principali.
- Engine: grafo, validazione, planner a livelli, state machine, retry/timeout/cancellazione.
- Registry nodi + provider; contratti di dominio per nodi, dati, pipeline ed esecuzioni.
- `PipelineExecutor` in-process con input binding dagli edge, esecuzione per livelli, failure/skip, artifact e metriche.
- Nodi reali: document source, semantic chunking, embeddings deterministici, vector index in-memory, query input, hybrid retrieval, reranker lessicale, generazione estrattiva.
- `pl_real_rag`: pipeline dimostrativa con embedding, reranking e generazione tramite Hugging Face, Ollama o OpenAI (hook provider reali, senza fallback reference).
- SSE `/executions/:id/stream` collegata all'esecuzione reale.
- `ExecutionResult` costruito dagli output reali (documenti, lineage, node outputs, embedding inspector, runtime breakdown).
- Artifact retrieval con URL e contenuto (`/executions/:id/artifacts/:artifactId` e `/content`) e listing (`/executions/:id/artifacts`).
- Persistenza DB di `ExecutionResult` e degli artifact refs: in modalità `database` le letture usano le tabelle come source-of-truth, con mirror in memoria come fallback.
- Persistenza DB di pipeline/liste/CRUD: `/pipelines` usa il repository SQLAlchemy come source-of-truth in modalità `database` (snapshot API lossless + seeding automatico dei demo), con mirror in memoria come fallback.
- Node executions persistiti su `node_executions` e proiettati via `GET /api/v1/executions/:id/nodes`; fallback dallo snapshot API per esecuzioni seed.
- `CancellationToken` live passato a ogni nodo: i nodi reference cooperano alle cancellazioni durante il lavoro, non solo tra nodi.
- `TimeoutPolicy`/`RetryPolicy` applicate nell'executor per nodo ed esecuzione, con eventi di retry/timeout e default configurabili via settings.
- Override per-nodo via `PipelineNode.config` (`timeoutSeconds`, `retryMaxAttempts`, `retryBackoffSeconds`).
- `execution_max_parallel_nodes`: nodi indipendenti di uno stesso livello eseguiti in parallelo con semaforo (default 4).
- Stream idempotente: `StreamCoordinator` condiviso, lock in-memory di default e lock Redis `SET NX EX` + pub/sub per deploy multi-worker; client concorrenti/riconnessi attendono e rileggono lo snapshot finale invece di rieseguire.
- `execution_max_parallel_executions`: limiter globale delle esecuzioni (semaforo in-memory o zset Redis con TTL per slot stale); mentre il client attende uno slot riceve `status: queued`.
- Storage artifact `filesystem`: contenuto durevole su disco con checksum, ref relativi e retention automatica (`ARTIFACT_ROOT_DIR`, `ARTIFACT_RETENTION_DAYS`); le API espongono sempre URL proxy HTTP, mai percorsi `file://`.
- Run con query override: `POST /pipelines/:id/run` con body opzionale `{query, inputs}`.
- Algoritmi come funzioni pure stdlib in `app/components/algorithms.py`, condivise da runtime, confronto ed export: chunking `fixed|recursive|sentence`, retrieval `hybrid|dense|bm25|rrf`, reranking `lexical|diversity|none`, generazione `extractive|first|concise`. Le varianti si selezionano dai parametri dei nodi esistenti (`chunkStrategy`, `retrievalAlgorithm`, `rerankStrategy`, `generationStrategy`, `maxSentences`), senza nuova architettura.
- `POST /api/v1/comparison/run`: stessa query, più varianti, risultati affiancati con risposta, citazioni, documenti, metriche e durata. UI nella sezione “Confronta varianti RAG” di `ExperimentsPage`.
- `GET /api/v1/pipelines/:id/export?format=python&query=...`: script standalone (solo stdlib) con le funzioni pure, `PIPELINE_CONFIG` derivato dal grafo e `main()` con CLI `query` e flag `--json`. Pulsante “Export .py” nell'editor e voce nel menu TopBar. Nessuna sandbox: il codice è generato da template, non caricato dall'utente.
- Test: 94 passati (API, engine, runtime, persistenza DB, policy, parallelismo, coordinamento, limiter, storage artifact, varianti algoritmiche, confronto reale ed eseguibilità dello script export), più i test mirati dell'audit API/security.

## Scelta architetturale: infrastruttura opt-in

`coordination.py`, `filesystem_store.py`, i repository SQLAlchemy e il wiring DB/Celery/MinIO restano nel progetto per sviluppi futuri, ma **non sono richiesti dal percorso principale**. I default sono `PERSISTENCE_BACKEND=memory`, `ARTIFACT_STORE_BACKEND=memory`, `STREAM_COORDINATION_BACKEND=memory`: il confronto algoritmico e l'export funzionano in un solo processo, senza servizi esterni. Nessun rollback dell'infrastruttura; dettagli e conseguenze in `DECISIONS.md`.

## P0 — Affidabilità esecuzione e persistenza

Stato: **in corso**. Completati i punti 1, 2 (parziale), 3 (parziale: contenuto filesystem durevole + retention), 4 (parziale), 5 e 6 (semaforo nodi + limiter esecuzioni; resta una coda con priorità/persistente).

1. **Idempotenza dello stream**: `StreamCoordinator` con lock in-memory e Redis + pub/sub; un solo owner esegue, gli altri attendono e riproducono lo stato finale (con timeout e takeover se il lock scade).
2. **DB come source-of-truth**: esecuzioni, eventi, snapshot API, risultati, artifact refs, pipeline/liste/CRUD e node executions usano i repository SQLAlchemy. Resta da rendere durevole il contenuto degli output dei nodi (oggi refs su DB, contenuto in memoria).
3. **Persistenza risultati/artefatti**: `ExecutionResult` e artifact refs persistono su DB; contenuto durevole disponibile con backend `filesystem` (default consigliato per single-node, retention inclusa) o `minio`. Restano da persistere gli output completi dei nodi e da allineare la retention ai refs DB.
4. **Cancellazione reale**: token live propagato a `ExecutionContext` e rispettato dai nodi reference; estendere il controllo ai provider/stream futuri.
5. **Timeout/retry**: policy applicate nell'executor (node timeout, execution timeout, retry con backoff ed eventi), default da settings e override per-nodo via `PipelineNode.config`.
6. **Gestione concorrenza**: semaforo per `execution_max_parallel_nodes` (parallelo entro un livello) e `execution_max_parallel_executions` (limiter globale con slot Redis TTL); resta una coda persistente con priorità e backpressure esplicita.

## P1 — Worker e streaming scalabile

1. Implementare `execute_pipeline` in Celery usando `PipelineExecutor` nel processo worker.
2. Event bus Redis pub/sub per eventi di esecuzione; SSE legge dal bus invece che dallo stato in-process.
3. Persistenza stato esecuzione prima/dopo ogni transizione (crash recovery).
4. Endpoint/queue status e health dei worker.
5. Sostituire `asyncio` in-process con dispatch al worker quando `EXECUTION_BACKEND=celery`.

## P2 — Provider e nodi reali

Stato: **provider reali attivi**. `pl_real_rag` usa Hugging Face (`sentence-transformers`/`transformers`), Ollama (`ollama serve`, modelli `nomic-embed-text` e `llama3.2:1b`) e OpenAI (`OPENAI_API_KEY` o `PATCH /providers/settings`). La selezione avviene per capability dalla configurazione del nodo, senza cambiare i contratti API.

1. **Fatto** — adattatori Ollama, OpenAI-compatible e Hugging Face per embedding/reranking/generazione.
2. **Fatto** — `ProviderRegistry` con risoluzione per capability, configurazione salvata in `backend/data/provider_settings.json` e chiavi mai restituite dalle API.
3. Da completare: `POST /models/:id/test` e registrazione modelli con esecuzione reale.
4. Da fare: adattatore vector store (Qdrant/Chroma) con `upsert`/`search`; oggi l'indice resta in-memory e Qdrant non è attivo.
5. Parziale: i dataset sincronizzano solo metadati e il testo viene letto dal connettore a runtime; manca un job di indicizzazione persistente (parse/chunk/embed).
6. **Fatto** — scelta del provider per nodo (`embedding.provider`, `rerank.provider`, `generation.provider`) mantenendo i contratti.

## P3 — Custom node runtime isolato

1. Esecuzione in subprocess/container con limiti CPU/memoria/tempo e rete disabilitata di default.
2. Gestione dipendenze e ambienti per versione del nodo.
3. Test/publish/version restore reali con artifact dei risultati.
4. Firma/validazione del codice e allowlist di import.

## P4 — Evaluation ed esperimenti reali

Stato: **in corso**. Il confronto reale tra varianti sulla stessa query è disponibile via `POST /comparison/run`; restano le valutazioni su dataset etichettati e la persistenza dei run.

1. Eseguire valutazioni su pipeline + dataset con metriche (faithfulness, relevance, precision, recall).
2. Persistere run, risultati per domanda, trend e confronti.
3. Promozione esperimento -> pipeline/versione.
4. Export report server-side.

## P5 — Integrazione frontend

1. Smoke test CI con `VITE_USE_MOCKS=false` contro backend reale.
2. UI per impostare la query di run e visualizzare artifact/risultati reali (la query e i risultati del confronto varianti sono già nella sezione “Confronta varianti RAG”).
3. Reconnect/retry SSE e stato esecuzione coerente dopo refresh.
4. Code splitting del bundle (oggi ~4.7 MB main chunk) e lazy loading di Monaco.
5. Gestione errori/empty state per pipeline senza retrieval/generation.

## P6 — Observability e sicurezza

Stato: **in corso**. `app_debug` è disattivato di default, `API_ACCESS_TOKEN` abilita l'header obbligatorio `X-API-Token` sui metodi mutanti prima di esporre la API in rete, i connettori locali sono limitati a `DATASET_ALLOWED_ROOTS` (con esclusione dei file di configurazione), i connettori HTTP bloccano reti private e redirect cross-host non autorizzati, i segreti dei dataset sono redatti in ogni risposta e il salvataggio JSON è atomico.

1. OpenTelemetry traces/metrics/log correlation (config già presente).
2. Log strutturati e correlation id per execution/node.
3. Fatto (parziale): redazione dei secret nelle risposte; resta la cifratura a riposo.
4. Fatto (parziale): token API mutanti; restano ruoli workspace e rate limiting.
5. Audit trail delle mutazioni.

## Gate di validazione

Da `backend/`:

```powershell
python -m pytest -q
```

Da `frontend/`:

```powershell
npm run build
```

Prima di avanzare di fase: test verdi + smoke test frontend contro API reale + documentazione contratti aggiornata.

## Nota sui limiti attuali

- In modalità `memory` i dati si resettano al riavvio del backend; in modalità `database` risultati e artifact refs sono persistenti.
- `pl_hybrid_rag` usa algoritmi deterministici (`hash-sha256-128`, `lexical-heuristic`, `extractive-reference`) e indice in-memory; `pl_real_rag` usa modelli reali HF/Ollama/OpenAI quando configurati. Qdrant e GPT-4o non sono il default attivo.
- Il contenuto degli artifact resta in-memory di default; MinIO è predisposto ma non è il default (i refs sono persistenti su DB).
- Celery e i task worker sono placeholder.
- Il runtime custom-node isolato non è ancora implementato.
