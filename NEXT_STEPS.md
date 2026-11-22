# Stato e prossimi passi

Branch corrente: `fix/wave2-real-features` (worktree `D:\github\Rag_studio-wave2`).
Base: `main` a `ecea00c` (include Wave 0 + Wave 1, merge `ecea00c`).
**Questo branch non è ancora stato mergiato né pushato.**

La cartella `Data/` (241 MB di PDF) è stata rimossa dalla history e aggiunta a `.gitignore`: i PDF restano solo sul disco locale.

## Verifiche correnti

- `cd backend && python -m pytest -q` → **467 passed** (0 warning Pydantic)
- `cd frontend && npx tsc -b --pretty false` → OK
- `cd frontend && npm run build` → OK (bundle 4,78 MB, warning Vite sul chunk >500 kB)

## Completato — Wave 0 + Wave 1 (già mergiate in `main`)

Hardening produzione (auth e root obbligatori, cifratura Fernet di `provider_settings.json`, fail fast dell'infrastruttura), nodi senza implementazione marcati `failed`, `bm25_scores` de-duplicato, 404 reale per custom node sconosciuti, UI onesta (`accent` applicato, niente toast/valori finti). Dettagli nei commit `f5546fb`…`dd6d774`.

## Completato in questo branch — Wave 2

| # | Intervento | Stato |
|---|---|---|
| 1 | `POST /models/{id}/test` | Ora usa resolver/hooks reali, latenza `perf_counter`, token solo dall'usage del provider, costo da token reali; provider reference → 503; nuovi campi `provider`, `providerModel`, `tokensAvailable`, `usageNote` |
| 2 | `POST /evaluations/run` | Calcola metriche reali da un `ExecutionResult` esistente (`executionId` o ultimo risultato); senza output reale → 409; nessuno score uguale alla soglia |
| 3 | `/experiments/compare` e `/promote` | Delta calcolati da risultati reali; missing results → 409; promote aggiorna esperimento, pipeline collegata, `promoted`/`promotedAt` |
| 4 | `GET/PATCH /settings/workspace` | Persistenza atomica su `backend/data/workspace_settings.json` con validazione Pydantic; file corrotto → errore esplicito; file ignorato da git |
| 5 | Custom node `test`/`tests`/`test-results` | `501` esplicito con richiesta di runtime isolato; UI non invia più richieste finte né mostra "test passes" simulati |
| 6 | Task Celery `execute_pipeline`/`execute_node` | Eseguono davvero engine/registry, ritornano metadati serializzabili, propagano errori; custom node rifiutato senza sandbox |
| 7 | `peakMemoryMb` | Misurato con `tracemalloc` (start/stop solo se non già attivo), arrotondato a 2 decimali; schema portato a `float` |
| 8 | Regressione DB risultati | Corretta: il float in campo `int` faceva fallire la validazione del snapshot DB e il fallback 404 |

Test nuovi: `test_wave2_apis.py` (8), `test_wave2_workspace.py` (7), `test_wave2_workers.py` (12), più aggiornamenti a `test_postmerge_correctness.py` e `test_audit_api_fixes.py`.

## Limiti noti

- **Smoke con provider reali non eseguito**: servono Ollama attivo o credenziali HF/OpenAI. I test usano fake provider e non dimostrano una chiamata rete reale.
- Celery non è installato nell'ambiente di sviluppo: i task sono callable e testati, ma il dispatch via broker non è stato provato. `docker-compose.yml` avvia il worker.
- La persistenza workspace è su file JSON locale (single-user), non su database condiviso.
- L'esecuzione di custom node resta deliberatamente non implementata: `501` invece di un runner insicuro.

## Prossimi passi — Wave 3 (qualità e delivery)

1. CI GitHub Actions: `pytest`, `tsc -b`, `npm run build` su ogni PR.
2. Script `lint` definito ma ESLint non installato → aggiungere dipendenza e config, o rimuovere lo script.
3. Nessun test frontend → Vitest su `portCompatibility`, `settings.api`, `usePipelineStore`.
4. Mock adapter incompleto (`/health`, `/settings/*`, `/providers/*`, PATCH modelli) e valida/run che ignorano il grafo inviato.
5. `TechniquesPage` filtra 552 tecniche nel browser → usare i query params già esposti dal backend.
6. Bundle >4,7 MB → lazy loading delle route e import dinamico di Monaco.
7. Smoke reale di `pl_real_rag` su `ds_133ebd5c` con Ollama/HF/OpenAI: richiede modelli o credenziali.
8. Valutare un runtime isolato (container/process sandbox) per i custom node, oggi dichiarato 501.

## Decisioni ancora aperte

- Scegliere dove custodire `PROVIDER_SETTINGS_KEY` (secret manager o keyring OS).
- Confermare se la persistenza workspace debba passare a database in deployment multi-utente.
- Fornire credenziali/modelli per lo smoke reale dei provider.
