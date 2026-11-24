# Stato e prossimi passi

Branch corrente: `main`.
Base: `main` a `ac2cd3f` (include Wave 0 + Wave 1 + Wave 2 + Wave 3, fix reranker, persistenza pipeline, pipeline HF pronta e fallback esplicito).
CI GitHub Actions: run #1 `45048225047` completato con successo.

La cartella `Data/` (241 MB di PDF) è stata rimossa dalla history e aggiunta a `.gitignore`: i PDF restano solo sul disco locale.

## Verifiche correnti

- `cd backend && python -m pytest -q -p no:logfire` → **546 passed** (inclusi database, `query-input`, preflight, pipeline ESG con tool Docker su localhost, risultati intermedi, offload dell'event loop, streaming parallelo, risoluzione password Neo4j, fusione multi-query di Hybrid Retrieval, candidati grafo validi per il reranker e metriche reali nei nodi strutturati)
  - Il plugin pytest `logfire` installato in questo ambiente è rotto (`ImportError: cannot import name '_ExtendedAttributes' from 'opentelemetry.util.types'`); va disabilitato con `-p no:logfire`. La verifica CI in virtualenv pulito con `backend/requirements-ci.txt` non è stata rieseguita dopo questa wave: ultimo risultato noto **468 passed** (dipendenze ML pesanti escluse: import lazy nei provider).
- `cd frontend && npx tsc -b --pretty false` → OK
- `cd frontend && npm run lint` → OK (0 errori)
- `cd frontend && npm run test:run` → **54 test Vitest passed** (16 file, inclusi runtime di esecuzione attiva, API risultati/nodi/artifact e vista mista *Intermediate results*)
- `cd frontend && npm run build` → OK. Bundle iniziale **706,79 kB** (era 4.785,82 kB); Monaco è ora un chunk separato da 3,33 MB caricato solo quando si apre l'editor. Resta il warning Vite sui chunk >500 kB (Monaco e Recharts), atteso e non bloccante.

## Completato — Wave 0 + Wave 1 (già mergiate in `main`)

Hardening produzione (auth e root obbligatori, cifratura Fernet di `provider_settings.json`, fail fast dell'infrastruttura), nodi senza implementazione marcati `failed`, `bm25_scores` de-duplicato, 404 reale per custom node sconosciuti, UI onesta (`accent` applicato, niente toast/valori finti). Dettagli nei commit `f5546fb`…`dd6d774`.

## Completato — Wave 2 (già mergiata in `main`, merge `5a026ef`)

| # | Intervento | Stato |
|---|---|---|
| 1 | `POST /models/{id}/test` | Usa resolver/hooks reali, latenza `perf_counter`, token solo dall'usage del provider, costo da token reali; provider reference → 503 |
| 2 | `POST /evaluations/run` | Metriche reali da un `ExecutionResult` esistente; senza output reale → 409 |
| 3 | `/experiments/compare` e `/promote` | Delta da risultati reali; missing results → 409; promote aggiorna esperimento e pipeline collegata |
| 4 | `GET/PATCH /settings/workspace` | Persistenza atomica su `backend/data/workspace_settings.json` con validazione Pydantic |
| 5 | Custom node `test`/`tests`/`test-results` | `501` esplicito con richiesta di runtime isolato; UI non invia richieste finte |
| 6 | Task Celery `execute_pipeline`/`execute_node` | Eseguono davvero engine/registry, ritornano metadati serializzabili |
| 7 | `peakMemoryMb` | Misurato con `tracemalloc`; schema portato a `float` |

## Completato — Wave 3 (già mergiata in `main`, merge `35bcb4d`)

| # | Intervento | Stato |
|---|---|---|
| 1 | CI GitHub Actions | `.github/workflows/ci.yml`: backend `pytest`, frontend `lint`, `test:run`, `tsc -b`, `build` su push a `main`, PR e `workflow_dispatch` |
| 2 | Dipendenze CI backend | `backend/requirements-ci.txt`: set minimale verificato in virtualenv pulito; esclude `sentence-transformers`/`transformers`/`torch` (import lazy) |
| 3 | ESLint | Config flat `frontend/eslint.config.js` + script `lint`; 0 errori su tutto il frontend |
| 4 | Test frontend | Vitest + jsdom: `portCompatibility` (9), `settings.api` (2), `usePipelineStore` (6), `techniques.api` (2), `mock/adapter` (6) |
| 5 | Mock adapter allineato | Aggiunti `/health`, `/settings/workspace` GET/PATCH, `/providers/settings|status|test`, `PATCH /models/:id`, 404 per pipeline sconosciute, valida/run/duplicate sul grafo richiesto, filtri `/techniques` come il backend. I test provider del mock non fingono successo |
| 6 | Filtri tecniche server-side | `TechniquesPage` usa i query params del backend con search debounced; statistiche dai conteggi aggregati `summary` invece di filtrare 552 tecniche nel browser |
| 7 | Code splitting | Tutte le route lazy-loadate; Monaco importato dinamicamente con worker locale condiviso; bundle iniziale −85% |

## Completato in questo branch — smoke HF reale e fix reranker

| # | Intervento | Stato |
|---|---|---|
| 1 | Smoke reale `pl_real_rag` su `ds_133ebd5c` | `POST /api/v1/comparison/run` con `pipelineId=pl_real_rag`, `datasetId=ds_133ebd5c`, query *"What are Eni's Scope 1 and Scope 2 greenhouse gas emissions in 2025?"* → **200 OK**, `durationMs=24491.1`, `documents=12`, `chunks=1578`, `dimensions=384`, `retrieved=20`, `selected=5`, 5 citazioni. Nessun `reference: true` e nessun fallback: embedding/reranking/generazione hanno usato i modelli HF default (`BAAI/bge-small-en-v1.5`, `cross-encoder/ms-marco-MiniLM-L-6-v2`, `google/flan-t5-small`) risolti da `auto`. `HF_TOKEN` non presente né necessario; i modelli erano già in cache e `huggingface.co` rispondeva HTTP 200. |
| 2 | Bug trovato dallo smoke | `HuggingFaceReranker.rerank()` passava `truncation=` a `CrossEncoder.predict()`: con `sentence-transformers 3.4.1` il metodo non accetta quella keyword → 500. Ora la configurazione viene passata come `tokenizer_args` in costruzione quando supportata, e `predict` riceve `truncation` solo se la firma lo consente. Aggiunto test di regressione senza modelli reali. |
| 3 | Setup locale dello smoke | I 12 PDF del dataset (241 MB) sono stati collegati via hard link dalla cartella locale `D:\github\RagSystem\data\bronze` alla cartella ignorata `D:\github\Rag_studio\Data`, senza copiare nulla nel repo. La qualità della risposta resta limitata da `flan-t5-small` e dal cross-encoder english: il recupero ha privilegiato a2a/snam invece di eni. Non è un problema di fallback. |
| 4 | Smoke della pipeline pronta `pl_hf_ready` | `POST /api/v1/comparison/run` con la configurazione esplicita HF → **200 OK**, `durationMs=20546.4`, `documents=12`, `chunks=1578`, `dimensions=384`, `retrieved=20`, `selected=5`, 5 citazioni. Conferma che provider/modelli espliciti funzionano, non solo `auto`. |
| 5 | Compatibilità `transformers 5.x` | La task `text2text-generation` è stata rimossa: `HuggingFaceGenerator` ora prova la pipeline classica e, se non disponibile, usa direttamente `AutoTokenizer` + `AutoModelForSeq2SeqLM`. 2 test con fake transformers coprono entrambi i percorsi. |
| 6 | Risposta ridotta a `[1]` | Con `flan-t5-small` la generation copiava solo l'etichetta del chunk: tre varianti di prompt hanno dato `[1]`/`[2]`. La pipeline pronta usa ora `google/flan-t5-base`, scaricato una volta in cache HF; `HF_TOKEN` non richiesto. |
| 7 | Fallback estrattivo esplicito | Quando il modello restituisce solo un marcatore (`[1]`) o meno di 4 parole, la risposta viene sostituita da `Risposta estratta dal contesto: …` e il fatto è segnalato in `metadata.weak_model_fallback` e nei log. Valido sia nel nodo `Model generation` sia in `/comparison/run`. |
| 8 | Smoke finale dopo il fallback | Esecuzione reale di `pl_hf_ready` via `PipelineExecutor` → `status=completed`, `errors=0`, 5 citazioni, `weak_model_fallback=True`, testo leggibile. `/api/v1/comparison/run` → **200 OK**, `durationMs≈19.8s`, 12 documenti, 1578 chunk, 5 citazioni, stessa risposta estratta esplicita. |

## Completato in questo branch — persistenza pipeline salvate

| # | Intervento | Stato |
|---|---|---|
| 1 | Store JSON locale `backend/data/pipelines.json` | Scrittura atomica, validazione Pydantic, file ignorato da git, nessun segreto salvato |
| 2 | Editor → persistenza | `PATCH /api/v1/pipelines/{id}` scrive lo store in modalità `memory`; creazione, duplicazione ed eliminazione utente coordinate allo stesso file |
| 3 | Restauro lazy al riavvio | Demo seminate dal codice + override salvati applicati una sola volta al primo accesso |
| 4 | DB resta canonico | Con `PERSISTENCE_BACKEND=database` si continua a usare il repository SQL; lo store JSON non viene toccato |
| 5 | Errori espliciti | File corrotto o non leggibile → `ValueError`; nessun fallback silenzioso ai demo |
| 6 | Isolamento test | Fixture autouse con file temporaneo + 3 test di regressione (save/restore, create/delete, file corrotto) |
| 7 | Pipeline `pl_hf_ready` | Seed completo HF, valida, visibile in lista e pre-salvata in `backend/data/pipelines.json`; 2 test dedicati |

### Pipeline HF pronta da eseguire

Nuova pipeline seed `pl_hf_ready` — **"HF RAG — pronta da eseguire"**. È già presente nell'editor, nello store seed del codice e, su questa macchina, anche in `backend/data/pipelines.json`: apri la pipeline e clicca **Run**. Nessun campo da compilare; la query è già impostata su *"What are Eni's Scope 1 and Scope 2 greenhouse gas emissions in 2025?"*.

Configurazione già applicata:

| Nodo | Parametri |
|---|---|
| Document source (`rm_document`) | `dataset=ds_133ebd5c` |
| Semantic Chunking (`rm_chunking`) | `chunkStrategy=recursive` |
| Model embeddings (`rm_embeddings`) | `provider=huggingface`, `model=BAAI/bge-small-en-v1.5` |
| In-memory index (`rm_index`) | `collection=product_docs`, `distance=Cosine` |
| Hybrid Retrieval (`rm_hybrid`) | `retrievalAlgorithm=hybrid`, `top_k=20`, `fusion=rrf`, `selection=diversity`, `embeddingProvider=huggingface`, `embeddingModel=BAAI/bge-small-en-v1.5` |
| Model reranker (`rm_reranker`) | `provider=huggingface`, `model=cross-encoder/ms-marco-MiniLM-L-6-v2`, `top_n=5` |
| Model generation (`rm_llm`) | `provider=huggingface`, `model=google/flan-t5-base`, `contextStrategy=numbered` |

Query-input (`rm_query`) ha `query` e `placeholder` già valorizzati con la domanda sopraindicata. Nessun `HF_TOKEN` richiesto.

## Completato in questo branch — tab Runs nella dashboard

| # | Intervento | Stato |
|---|---|---|
| 1 | Tab **Run** in dashboard | `Panoramica` / `Run`, con conteggio esecuzioni e deep link `?tab=runs`; il contenuto inattivo resta smontato, quindi i run si caricano all'apertura della tab. |
| 2 | Elenco rapido | `executionsApi.list()` → `GET /api/v1/executions`: run dal più recente, stato, durata, pipeline, token, ricerca, filtro stato, paginazione e refresh automatico ogni 8s. Nessun endpoint `/runs` inventato. |
| 3 | Risultati e dettaglio | Clic su un run → `GET /api/v1/executions/{id}/results` con anteprima della risposta e metriche; link diretti a `/runs/:id` e `/runs/:id/results`. |
| 4 | Accessi multipli | Oltre alla tab: voce sidebar **Runs**, voce nella command palette e URL `/?tab=runs`. |
| 5 | Verifiche | `tsc`, lint, 33 test Vitest (8 file) e build OK; bundle iniziale 694,86 kB. |

## Completato in questo branch — connessioni a database esterni

| # | Intervento | Stato |
|---|---|---|
| 1 | Catalogo dichiarativo | `backend/app/components/database_catalog.py`: 24 database (10 vector, 7 relazionali, 2 documentali, 2 cache, 1 graph, 1 time-series, 1 search), porte/scheme/host Docker/percorsi e campi condizionali in un'unica fonte |
| 2 | Un nodo per database | `db-<database>` generati da catalogo; vector in `Vector Databases`, gli altri in `Databases`; il nodo `qdrant` in-memory resta invariato |
| 3 | Modalità e target | `mode` `local`/`remote` e `target` `embedded`/`localhost`/`docker`/`ip`; opzioni e visibilità dei campi dipendono dal database e dalla modalità; la UI corregge il target quando cambia `mode` |
| 4 | Derivazione | porta, protocollo, DSN, host Docker e valori predefiniti non chiesti all'utente; `missing` segnala solo i campi obbligatori rimasti; `public_dict()` maschera i secrets ed esclude `private_url` |
| 5 | API e contratti | `GET /databases/catalog`, `POST /databases/derive`, `POST /databases/test`; `ParamDefinition` estesa con `secret`, `derived`, `visibleWhen`, `optionsByMode`; documentate in `backend/API_CONTRACTS.md` |
| 6 | Probe ed esecuzione | HTTP health/TCP connect/file/SQLite; upsert Qdrant via REST; query SQL reali con `sqlite3`/SQLAlchemy; per gli altri DB `ConnectionRef` con warning esplicito, nessun falso successo |
| 7 | Frontend allineato | catalogo mock e 24 nodi nella libreria, inspector con input password/badge auto/pannello "Connessione derivata" e pulsante test; test mock sempre `ok:false` |
| 8 | Test | 15 test backend (`backend/tests/test_database_nodes.py`), test frontend dedicati per API/parametri/adapter; `tsc`, lint, 39 Vitest e build OK |

Le modifiche di questo branch sono ancora **non committate**.

## Completato in questo branch — eliminazione pipeline reale

| # | Intervento | Stato |
|---|---|---|
| 1 | Backend | `DELETE /api/v1/pipelines/:id` rimuove davvero la pipeline, demo incluse; un tombstone in `store.deleted_pipeline_ids` e nel file JSON locale impedisce che venga riseminata al riavvio |
| 2 | Mock adapter | `DELETE /pipelines/:id` rimuove la pipeline da lista, dettagli e created summaries, e restituisce 404 per id sconosciuti/già eliminati |
| 3 | Frontend | Nella tabella pipelines ogni riga ha un pulsante **trash** visibile che elimina subito la pipeline senza aprire l'editor; il menu `⋯` e il dialog di conferma restano disponibili; la lista si aggiorna tramite l'invalidazione della query |
| 4 | Dropdown portal | `DropdownMenuContent` ferma `pointerdown`/`click`: prima le voci del menu (renderizzate in portal) risalivano l'albero React fino all'`onClick` della riga e aprivano l'editor invece di eseguire l'azione |
| 5 | Editor grafico | Ogni nodo del canvas ha un pulsante **✕** *Rimuovi nodo* che elimina il blocco senza aprire l'inspector; la toolbar dell'editor ha un pulsante **Delete** (abilitato quando è selezionato un nodo o un collegamento), che condivide la stessa logica di `Delete`/`Backspace` e della voce *Delete selected node* del menu |
| 6 | Test | Aggiunti test di regressione backend (demo delete persistente, delete demo in modalità database), mock e UI (`RAGNode.test.tsx` per il nodo, `dropdown.test.tsx` per la propagazione del portal); backend 508 passed, frontend 42 Vitest, tsc, lint e build OK (conteggi di quella fase; finali in “Verifiche correnti”) |

## Completato in questo branch — parametri di Query input

| # | Intervento | Stato |
|---|---|---|
| 1 | Causa | Con il backend reale l'inspector mostrava solo `placeholder` perché `NodeDefinition`/`NodeSpec` di `query-input` dichiaravano quel solo parametro, mentre `QueryInputNode.execute()` leggeva già `config["query"]`. Il catalogo mock, invece, esponeva `query` e `variables`. |
| 2 | Backend | `query`, `variables` e `placeholder` aggiunti alla definizione in `store.py` e alla `QueryInputNode.spec()`; il default di `query` usa `algorithms.DEFAULT_QUERY`, lo stesso valore usato dal runtime e dal mock |
| 3 | Frontend | Il catalogo mock espone ora gli stessi tre parametri, così la UI è identica con backend reale e mock |
| 4 | Test | `backend/tests/test_query_input_parameters.py` verifica i parametri via `/api/v1/nodes`, nella `NodeSpec` e l'uso effettivo di `config["query"]` in `execute()`; backend 518 passed, frontend 42 Vitest, tsc, lint e build OK (conteggi di quella fase; finali in “Verifiche correnti”) |

## Completato in questo branch — ambienti locali e tool Docker

| # | Intervento | Stato |
|---|---|---|
| 1 | Causa UI non caricata | Le porte 8000 e 5173 erano occupate dai container `backend`/`frontend` di `progetti/docker-compose.yml`, non dai processi locali. I PDF in `Data\` non sono dentro quei container, quindi il backend dockerizzato richiedeva la riscrittura dei percorsi fatta in fase di build. |
| 2 | Docker solo tool | `progetti/docker-compose.yml` ora avvia solo `qdrant` e `neo4j`; i servizi `backend`/`frontend` e i volumi HF/artifact sono stati rimossi. I container rimasti sono pubblicati su `localhost:6333` e `localhost:7474`. |
| 3 | Backend/frontend locali | Il backend gira da `backend/` con `uvicorn --reload --host 127.0.0.1 --port 8000`; il frontend da `frontend/` con `npm run dev`. `frontend/.env` continua a proxyare `/api` su `http://localhost:8000`. |
| 4 | Configurazione | `backend/.env` imposta `NEO4J_PASSWORD`, `NODE_TEST_TIMEOUT_SECONDS=20` e i timeout allargati per l'embedding CPU; `DATASET_ALLOWED_ROOTS` resta vuoto perché il default include già la root del repo (con `Data\`) e il temp di sistema. Le pipeline ESG usano `db-qdrant` con `mode=local`, `target=localhost`, `host=127.0.0.1` e `kg-writer` su `127.0.0.1:7474`. |
| 5 | Documentazione | Aggiornati `progetti/README.md` e `guidaAvvio.md`; `progetti/docker/prepare.py` non è più necessario nel flusso predefinito. |
| 6 | Fix probe Neo4j | Il test del nodo *Neo4j graph writer* rispondeva 401 perché `NEO4J_PASSWORD` era letto da `os.environ`, che pydantic-settings non popola leggendo `.env`. Ora `neo4j_password()` in `app/core/config.py` risolve config del nodo → `settings` → env; usata sia dal probe che da `kg-writer`. Test live: `ok:true` in 53 ms con config vuota, 401 solo con password esplicita errata |
| 7 | Fix Hybrid Retrieval | *Hybrid Retrieval failed: cannot access free variable 'index'* nella pipeline ESG RAG-Fusion: `retrieve_extended` in `app/components/algorithms.py` riutilizzava `index` della comprensione fuori dal suo scope nella fusione multi-query, e indicizzava gli score con il numero della variante invece della posizione dell'item. Ora ordina le posizioni in `items` con `sorted(range(len(items)), key=...)`. Regressioni: livello algoritmo (`test_algorithms_extended.py`) e livello nodo (`test_audit_rag_fixes.py`, `queryExpansion=multi_query` + `embeddingProvider=reference` con item reali) |
| 8 | Fix Model reranker | *Un candidato non contiene testo utilizzabile*: il `Graph retriever` emetteva hit `{"id","label","score","hops"}` senza `content`, e il modello copiava dal prompt l'entità segnaposto `"..."` che finiva anche su Neo4j. Ora `normalize_graph` scarta segnaposto (`...`, `n/a`, `example`, …), `graph_retrieve` genera `content` da etichetta/tipo/relazioni, e `ProviderRerankerNode` salta i candidati senza testo con warning e `metrics.skipped` invece di far fallire tutta la pipeline. Replay live con il cross-encoder HF reale: `status=completed`, 2 candidati rerankati, 1 saltato, 18,7 s |
| 9 | Fix inspector output strutturati | `ESG knowledge graph extractor`, `Answer evaluator`, `Citation verifier` e `Corrective gate` mostravano `Document 1 —` perché `result_builder` trattava qualsiasi output non-lista come documento e non leggeva `out_metrics`/`out_decision`/`out_graph`. Ora i nodi con porte JSON mostrano titoli reali e anteprime JSON (con secret mascherati), le metriche vengono lette dagli output reali (`groundedness=86,5%`, `completeness=40,0%`, `Decisione=accept`, `Nodi grafo`, `Provider`/`Modello`) e `Strategia` compare solo se presente. `Qdrant connection` legge `out_index` invece di `out_connection` (`Vettori`, `Distanza`, `Dimensioni`). `Document component extraction` resta renderizzato come documenti perché ha testo reale. 5 regressioni in `test_execution_engine.py` |

## Completato in questo branch — run attivo durante la navigazione

| # | Intervento | Stato |
|---|---|---|
| 1 | Causa | Lo stream SSE era di proprietà della pagina: aprendo *Risultati* l'editor si smontava, chiudeva l'unico consumer e il backend lasciava il run in stato non terminale; tornando indietro lo stato locale `running`/`nodeStatus` era stato azzerato da `loadPipeline()`. Inoltre `/executions/:id/results` rispondeva 404 finché il run non era finalizzato, quindi aprire i "parziali" mostrava un errore generico (ora i risultati parziali vengono persistiti a ogni nodo, vedi sezione seguente). |
| 2 | Runtime globale | `frontend/src/lib/activeExecution.ts` possiede un solo EventSource per app, distribuisce snapshot a editor, monitor e StatusBar, sopravvive al cambio pagina e si riconnette dopo un ricaricamento tramite `sessionStorage`. |
| 3 | Pagine | Editor e monitor leggono lo stato dal runtime invece di aprire stream propri; `PipelinesPage` avvia il runtime quando fa partire un run (prima il run restava `queued` senza consumer). La StatusBar mostra "Run in corso · N/T" cliccabile. |
| 4 | Risultati | `ResultsPage` interroga lo stato del run e `/results` anche durante l'esecuzione: i nodi finiti mostrano output reali, gli altri "in corso/in attesa"; banner di progresso e link al monitor al posto dell'errore 404. |
| 5 | Test | 5 test Vitest nuovi in `activeExecution.test.ts`; frontend 54 test / 16 file, tsc, lint e build OK (conteggi finali in "Verifiche correnti"). |

## Completato in questo branch — risultati intermedi e backend reattivo

| # | Intervento | Stato |
|---|------------|-------|
| 1 | Persistenza parziale | Dopo ogni nodo `completed`/`failed`/`skipped` il backend salva un `ExecutionResult` parziale con lo stesso `build_execution_result` del risultato finale; `/executions/:id/results` risponde 200 già durante il run e `_finalize` sovrascrive con il risultato completo |
| 2 | Artifact live | Gli artifact dei nodi sono registrati subito a `node_completed`; `persist_execution_artifacts` normalizza le ref da port-keyed ad artifact-id-keyed e `store.save_execution_artifacts` fa merge invece di replace, così il contenuto è leggibile prima del finalize |
| 3 | Vista mista | `ResultsPage` mostra gli step completati come nella vista finale e i nodi rimanenti come "in corso/in attesa", con banner di progresso e polling ogni 1,2 s finché il run è attivo; test dedicati in `ResultsPage.test.tsx` e `executions.api.test.ts` |
| 4 | Reattività event loop | Wrapper async dei resolver con `asyncio.to_thread`, cache dei modelli invalidata da `save_settings()`, offload dei nodi CPU-bound, del confronto API e del probe Ollama: il backend serve richieste non correlate mentre una pipe gira. Regressioni in `test_event_loop_offload.py` |
| 5 | Streaming parallelo | Con `max_parallel_nodes=4` il vecchio `asyncio.gather` bufferava tutti gli eventi di un livello: ora `executor.stream` usa una coda e un task per nodo, emettendo `node_started`/`node_completed` appena disponibili. Test di regressione in `test_intermediate_results.py` |
| 6 | Verifica live | Run reale di `pl_hf_ready` con consumatore SSE: `/health`, `/pipelines`, `/executions` sempre 200 (`n=273`, `min=1.0 ms`, `avg=68.4 ms`, `p95=213.6 ms`, `max=350.6 ms`); `Query input` risulta `completed` a 0,02 s con 1 step in `/results` mentre `Document source` è ancora `running` |

## Limiti noti

- Lo smoke HF dimostra il percorso reale con modelli pubblici in cache; Ollama e OpenAI restano non provati. I test automatici continuano a usare fake provider per non dipendere dalla rete.
- La risposta resta limitata da `google/flan-t5-base` e dal cross-encoder english: il modello è più capace di `small`, ma non è un LLM multilingua. Per qualità superiore servono modelli più grandi o un LLM Ollama/OpenAI.
- Celery non è installato nell'ambiente di sviluppo: i task sono callable e testati, ma il dispatch via broker non è stato provato. `docker-compose.yml` avvia il worker.
- La persistenza workspace e quella delle pipeline salvate sono ora su file JSON locale (single-user), non su database condiviso.
- In `PERSISTENCE_BACKEND=memory` restano volatili esecuzioni e modelli registrati via API; sopravvivono solo le pipeline salvate. In `database` il DB resta la fonte canonica.
- I run HF locali mostrano `tokens: 0`: il provider non riporta ancora l'usage reale; non significa che il modello non abbia lavorato.
- L'esecuzione di custom node resta deliberatamente non implementata: `501` invece di un runner insicuro.
- Il chunk Monaco rimane >500 kB: è caricato solo su richiesta; il warning Vite è informativo.
- Il backend esegue il DAG mentre viene consumato lo stream SSE: navigare dentro l'app o ricaricare la pagina è coperto dal runtime globale, ma chiudere del tutto il browser interrompe il run e va riaperto il monitor per riattraccarlo (con ripartenza dal primo nodo, perché il backend non supporta ancora il resume).
- I nodi database hanno probe reali, ma adapter di lettura/scrittura dedicati solo per Qdrant (REST) e SQL (SQLite/SQLAlchemy). Per gli altri database il nodo restituisce un `ConnectionRef` con avviso: va aggiunto un adapter per ogni SDK, senza inventare risultati.
- Il probe TCP verifica la porta, non il protocollo o le credenziali: un successo HTTP/TCP non garantisce che il client specifico riesca a fare query.
- Le credenziali dei nodi database restano nella configurazione in memoria del nodo (non in artifact/API); per un deployment multi-utente servono secret store e mascheramento della configurazione salvata.
- In `PERSISTENCE_BACKEND=database` i tombstone delle pipeline eliminate vivono solo in memoria: se si eliminano tutte le pipeline e si riavvia, `_ensure_seeded` può riseminare le demo. Per un deployment condiviso servono tombstone persistiti nel DB.

## Prossimi passi (fuori da Wave 3)

1. Aprire `pl_hf_ready` nell'editor e cliccare **Run**: non serve configurare nulla. Stato e risultati sono subito visibili nella dashboard → tab **Run** (o `/?tab=runs`).
2. Confermare visivamente nel browser la vista mista *Intermediate results* durante un run reale: finora la verifica è via test component e dati API live (questo ambiente non ha browser/screenshot).
3. Ripetere lo smoke con Ollama o OpenAI (e con modelli HF più grandi) per confrontare la qualità della generazione; l'infrastruttura è già verificata con HF.
4. Valutare un runtime isolato (container/process sandbox) per i custom node, oggi dichiarato `501`.
5. Eseguire il workflow CI su GitHub dopo il push e verificare i badge.
6. Eventuale manual chunking di Recharts per eliminare il residuo chunk da 382 kB.
7. Aggiungere adapter di lettura/scrittura per i database ancora limitati a `ConnectionRef`, partendo da Chroma, Redis e MongoDB; mantenere il catalogo come unica fonte di verità.
8. Provare il probe e l'esecuzione dei nodi database contro istanze reali locali/Docker (Qdrant e PostgreSQL già coperti a livello di test) prima di usare IP remoti.
9. Decidere dove custodire le credenziali dei nodi database in un deployment multi-utente, senza esporle nelle risposte API o negli artifact.

## Decisioni ancora aperte

- Scegliere dove custodire `PROVIDER_SETTINGS_KEY` (secret manager o keyring OS).
- Confermare se la persistenza workspace debba passare a database in deployment multi-utente.
- Valutare se sostituire i modelli HF default con varianti più accurate per corpora italiani.
