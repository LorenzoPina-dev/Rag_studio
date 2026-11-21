# Decisioni architetturali

## Scopo del progetto

RAG Studio serve a creare pipeline RAG confrontabili, vedere cosa cambia al variare degli algoritmi ed esportare codice Python eseguibile. La complessità tecnica deve stare dietro le quinte: il percorso principale deve restare semplice, solido e utilizzabile in un solo processo.

## Backend avanzati: mantenuti ma opt-in

L'infrastruttura aggiunta nelle fasi precedenti non viene rimossa:

- `backend/app/infrastructure/coordination.py` (coordinamento stream e limiter esecuzioni, anche Redis);
- `backend/app/infrastructure/storage/filesystem_store.py` (artifact durevoli su disco, checksum e retention);
- backend DB, repository SQLAlchemy e wiring correlato.

Questa infrastruttura resta disponibile per sviluppi futuri, ma **non fa parte del percorso predefinito**:

- `PERSISTENCE_BACKEND=memory`;
- `ARTIFACT_STORE_BACKEND=memory`;
- `STREAM_COORDINATION_BACKEND=memory`.

Per attivarla basta cambiare le variabili d'ambiente; il flusso principale non la richiede e non ne dipende.

## Dataset di progetto

I dataset creati dalla UI sono dati di progetto e non metadati dimostrativi: vengono persistiti in `backend/data/datasets.json` come inventario di file, senza richiedere il backend database. Non esiste più l'import di testo/file dalla UI: l'utente sposta i file reali nella cartella (o bucket/endpoint) del connettore e poi fa Sync. Il nodo *Document source* legge il testo dal connettore a runtime e lo passa a chunking semantico, retrieval, reranking e generazione; confronto ed export usano lo stesso loader. I connettori remoti fanno fetch di testo/JSON (urllib, minio, SQLAlchemy già presenti) e non eseguono codice. Le credenziali restano in chiaro nel JSON locale: accettabile per il prototipo single-user, da rivedere prima di un uso multi-user.

## Inventario file e pipeline ibride

Il pulsante *Sync* su un dataset è una scansione di metadati: elenca i file senza estrarre testo e senza salvare `items`, quindi resta veloce anche con centinaia di PDF. Il risultato è visibile in **Datasets → Preview documents → File trovati dal connettore**. `Local files` usa `stat()` su ogni file e S3 usa `list_objects()` senza `get_object()`; per gli altri connettori, che non hanno un'API di listing, l'inventario è derivato dai record ricevuti. Per `Local files` e `S3` l'inventario include anche i file non parseabili (`indexed: false`, per esempio immagini), così l'utente vede cosa è stato scartato. Ogni dataset espone `files: DatasetFile[]` (`id`, `name`, `path`, `fileType`, `size`, `indexed`); `items` resta vuoto per i dataset con connettore ed è usato solo dai dataset inline legacy (senza path).

I PDF sono supportati nei connettori `Local files` e `S3` tramite `pypdf` (dipendenza dichiarata): una pagina senza testo non genera un documento vuoto ma un errore chiaro che segnala la necessità di OCR, non implementato. I PDF protetti da password vengono rifiutati con messaggio esplicito. L'estrazione avviene solo in `load_documents_for_dataset` (pipeline, confronto ed export) ed è limitata a 200 documenti e 8 milioni di caratteri per PDF, per evitare che un singolo file gigante blocchi il processo.

La selezione avviene nei nodi, non a monte: il nodo *Document source* ha i parametri `fileTypes` (`all`, `pdf`, `text`, `txt`, `md`, `json`, `jsonl`, `csv`, `documents`, `other`) e `fileName` (sottostringa o wildcard `*`). Il filtro è una funzione stdlib condivisa (`app/components/algorithms.py`) usata anche da confronto ed export, quindi le tre strade non possono divergere. Per creare rami diversi basta più nodi *Document source* con filtri diversi: il motore supporta già fan-out/fan-in, e il nodo `merge-documents` ricompone due rami (`in_documents_a`, `in_documents_b`) deduplicando per id prima di chunking/embedding/retrieval.

`GET /api/v1/datasets` restituisce l'inventario completo e, per i soli dataset inline legacy, un'anteprima di 240 caratteri per documento. Non essendo più memorizzato il testo estratto, `backend/data/datasets.json` è passato da ~13 MB a ~10 KB e la lista risponde in ~0,08 s. I selettori leggeri usano `GET /api/v1/datasets/options`.

## Risultati per fase

`ExecutionResult.stepOutputs` espone, per ogni nodo eseguito, un campione limitato degli output reali (testo per query/risposta, item per documenti/chunk/embedding/candidati) e metriche calcolate per tipo (conteggi, lunghezze, token, score, dimensioni). La pagina Results usa questi dati per mostrare il debug della fase selezionata con ricerca locale su titolo, fonte, contenuto e metadati. Campioni e metadati sono limitati (`_SAMPLE_LIMIT`, `_CONTENT_LIMIT`) per non riempire il payload con documenti interi.

## Modelli reali e implementazioni di riferimento

I nodi che dichiarano un modello lo usano davvero: `app/providers/resolver.py` risolve Hugging Face → Ollama → OpenAI in quest'ordine e solleva `ProviderUnavailableError` se nessun provider è disponibile. Non esiste fallback silenzioso a vettori hash. Le credenziali si configurano da UI (`PATCH /api/v1/providers/settings`) o da variabili d'ambiente (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OLLAMA_BASE_URL`, `HF_*`) e vengono salvate in `backend/data/provider_settings.json`; `GET /api/v1/providers/settings` restituisce solo `openai_api_key: null` e `openai_api_key_set`, quindi la chiave non appare mai in codice, log o risposte API.

Le implementazioni deterministiche locali restano, ma hanno nomi onesti: `hash-sha256-128` (vettori SHA-256 a 128 dimensioni), `lexical-heuristic` (reranking euristico), `extractive-reference` (frasi copiate dal contesto) e `In-memory index (reference)` (dizionario Python, nessun Qdrant). Non sono modelli e nei risultati sono marcati `reference: true` con un avviso esplicito. `active_pipeline` (`pl_hybrid_rag`) resta la pipeline reference deterministica usata dai test; `pl_real_rag` è la pipeline con nodi provider reali (embedding, reranking e generazione).

Il cross-encoder Hugging Face viene importato da `sentence_transformers.cross_encoder.CrossEncoder`, con fallback a `transformers.CrossEncoder` solo per versioni precedenti: nelle versioni recenti `transformers` non esporta più quella classe. La pipeline di generazione `text2text-generation` usa `truncation=True` per rispettare il limite di 512 token di `flan-t5-small`.

## Algoritmi RAG estesi

`app/components/algorithms.py` ora copre chunking `fixed`, `recursive`, `sentence`, `token` e `parent-child`; BM25 parametrico, dense, RRF, MMR, fusione lineare/RRF, selezione `top_k`/`threshold`/`mmr`/`diversity`/`adaptive`, espansione `multi_query`/`decompose`/`hyde_prompt`, costruzione del contesto con budget di caratteri e metriche `recall`/`precision`/`MRR`/`nDCG`/`hit_rate`. Le stesse funzioni pure sono usate da runtime, confronto, nodi ed export. `run_pipeline(..., provider_hooks=...)` accetta hook reali senza mai sostituirli con hash: se il provider dichiarato non è `reference`, l'hook è obbligatorio.

## Conseguenze operative

- Il runtime predefinito resta in-process, senza Redis, MinIO, filesystem persistente o worker obbligatori.
- Le varianti algoritmiche devono stare in funzioni pure condivise tra runtime ed export, senza dipendenze esterne.
- Il chunking non è una proprietà del dataset: Sync non calcola chunk (`chunks` resta 0) e la strategia/dimensione si scelgono solo nel nodo *Semantic chunking* della pipeline. La pagina Datasets mostra statistiche sui file (tipi, dimensioni, stato), non conteggi di chunk.
- L'export Python di una pipeline reference resta standalone (solo stdlib). Una pipeline con provider reali genera `PROVIDER_CONFIG` e `provider_hooks`: lo script importa il layer provider di RAG Studio, non embedding SDK o chiavi. Non essendo codice caricato dall'utente, non serve una sandbox in questa fase.
- La sandbox andrà considerata solo se verranno eseguiti custom node con codice scritto dall'utente.
