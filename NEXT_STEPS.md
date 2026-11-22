# Stato e prossimi passi

Branch corrente: `main`.
Base: `main` a `ac2cd3f` (include Wave 0 + Wave 1 + Wave 2 + Wave 3, fix reranker, persistenza pipeline, pipeline HF pronta e fallback esplicito).
CI GitHub Actions: run #1 `45048225047` completato con successo.

La cartella `Data/` (241 MB di PDF) è stata rimossa dalla history e aggiunta a `.gitignore`: i PDF restano solo sul disco locale.

## Verifiche correnti

- `cd backend && python -m pytest -q` → **479 passed**
- Verifica CI in virtualenv pulito con `backend/requirements-ci.txt` → **468 passed** (dipendenze ML pesanti escluse: import lazy nei provider); la nuova wave è coperta dai 479 test dell'ambiente locale
- `cd frontend && npx tsc -b --pretty false` → OK
- `cd frontend && npm run lint` → OK (0 errori)
- `cd frontend && npm run test:run` → **33 test Vitest passed** (8 file)
- `cd frontend && npm run build` → OK. Bundle iniziale **694,86 kB** (era 4.785,82 kB); Monaco è ora un chunk separato da 3,33 MB caricato solo quando si apre l'editor. Resta il warning Vite sui chunk >500 kB (Monaco e Recharts), atteso e non bloccante.

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

## Limiti noti

- Lo smoke HF dimostra il percorso reale con modelli pubblici in cache; Ollama e OpenAI restano non provati. I test automatici continuano a usare fake provider per non dipendere dalla rete.
- La risposta resta limitata da `google/flan-t5-base` e dal cross-encoder english: il modello è più capace di `small`, ma non è un LLM multilingua. Per qualità superiore servono modelli più grandi o un LLM Ollama/OpenAI.
- Celery non è installato nell'ambiente di sviluppo: i task sono callable e testati, ma il dispatch via broker non è stato provato. `docker-compose.yml` avvia il worker.
- La persistenza workspace e quella delle pipeline salvate sono ora su file JSON locale (single-user), non su database condiviso.
- In `PERSISTENCE_BACKEND=memory` restano volatili esecuzioni e modelli registrati via API; sopravvivono solo le pipeline salvate. In `database` il DB resta la fonte canonica.
- I run HF locali mostrano `tokens: 0`: il provider non riporta ancora l'usage reale; non significa che il modello non abbia lavorato.
- L'esecuzione di custom node resta deliberatamente non implementata: `501` invece di un runner insicuro.
- Il chunk Monaco rimane >500 kB: è caricato solo su richiesta; il warning Vite è informativo.

## Prossimi passi (fuori da Wave 3)

1. Aprire `pl_hf_ready` nell'editor e cliccare **Run**: non serve configurare nulla. Stato e risultati sono subito visibili nella dashboard → tab **Run** (o `/?tab=runs`).
2. Ripetere lo smoke con Ollama o OpenAI (e con modelli HF più grandi) per confrontare la qualità della generazione; l'infrastruttura è già verificata con HF.
3. Valutare un runtime isolato (container/process sandbox) per i custom node, oggi dichiarato `501`.
4. Eseguire il workflow CI su GitHub dopo il push e verificare i badge.
5. Eventuale manual chunking di Recharts per eliminare il residuo chunk da 382 kB.

## Decisioni ancora aperte

- Scegliere dove custodire `PROVIDER_SETTINGS_KEY` (secret manager o keyring OS).
- Confermare se la persistenza workspace debba passare a database in deployment multi-utente.
- Valutare se sostituire i modelli HF default con varianti più accurate per corpora italiani.
