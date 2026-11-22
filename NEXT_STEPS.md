# Stato e prossimi passi

Branch corrente: `fix/hf-reranker-truncation` (worktree dedicato).
Base: `main` a `35bcb4d` (include Wave 0 + Wave 1 + Wave 2 + Wave 3).
CI GitHub Actions: run #1 `45048225047` completato con successo.

La cartella `Data/` (241 MB di PDF) è stata rimossa dalla history e aggiunta a `.gitignore`: i PDF restano solo sul disco locale.

## Verifiche correnti

- `cd backend && python -m pytest -q` → **468 passed**
- Verifica CI in virtualenv pulito con `backend/requirements-ci.txt` → **468 passed** (dipendenze ML pesanti escluse: import lazy nei provider)
- `cd frontend && npx tsc -b --pretty false` → OK
- `cd frontend && npm run lint` → OK (0 errori)
- `cd frontend && npm run test:run` → **25 test Vitest passed** (5 file)
- `cd frontend && npm run build` → OK. Bundle iniziale **694,53 kB** (era 4.785,82 kB); Monaco è ora un chunk separato da 3,33 MB caricato solo quando si apre l'editor. Resta il warning Vite sui chunk >500 kB (Monaco e Recharts), atteso e non bloccante.

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

## Limiti noti

- Lo smoke HF dimostra il percorso reale con modelli pubblici in cache; Ollama e OpenAI restano non provati. I test automatici continuano a usare fake provider per non dipendere dalla rete.
- La risposta dello smoke è in italiano ma parzialmente sconnessa: `google/flan-t5-small` è un modello molto piccolo e non multilingua; per una valutazione di qualità servono modelli più grandi (es. `google/flan-t5-base` o un LLM Ollama/OpenAI).
- Celery non è installato nell'ambiente di sviluppo: i task sono callable e testati, ma il dispatch via broker non è stato provato. `docker-compose.yml` avvia il worker.
- La persistenza workspace è su file JSON locale (single-user), non su database condiviso.
- L'esecuzione di custom node resta deliberatamente non implementata: `501` invece di un runner insicuro.
- Il chunk Monaco rimane >500 kB: è caricato solo su richiesta; il warning Vite è informativo.

## Prossimi passi (fuori da Wave 3)

1. Ripetere lo smoke con Ollama o OpenAI (e con modelli HF più grandi) per confrontare la qualità della generazione; l'infrastruttura è già verificata con HF.
2. Valutare un runtime isolato (container/process sandbox) per i custom node, oggi dichiarato `501`.
3. Eseguire il workflow CI su GitHub dopo il push e verificare i badge.
4. Eventuale manual chunking di Recharts per eliminare il residuo chunk da 382 kB.

## Decisioni ancora aperte

- Scegliere dove custodire `PROVIDER_SETTINGS_KEY` (secret manager o keyring OS).
- Confermare se la persistenza workspace debba passare a database in deployment multi-utente.
- Valutare se sostituire i modelli HF default con varianti più accurate per corpora italiani.
