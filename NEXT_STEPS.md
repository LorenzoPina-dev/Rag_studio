# Stato e prossimi passi

Branch corrente: `fix/post-merge-hardening` (worktree `D:\github\Rag_studio-postmerge`).
Base: `main` a `2444db4` (include merge `cddcc20`, fix audit `3c4d428`, catalogo tecniche `165ff9c`).
**Questo branch non è ancora stato mergiato né pushato.**

La cartella `Data/` (241 MB di PDF) è stata rimossa dalla history e aggiunta a `.gitignore`: i PDF restano solo sul disco locale.

## Verifiche correnti

- `cd backend && python -m pytest -q` → **440 passed**
- `cd frontend && npx tsc -b --pretty false` → OK
- `cd frontend && npm run build` → OK (bundle ancora >4,7 MB, warning Vite)

## Completato in questo branch (Wave 0 + Wave 1)

| # | Intervento | Stato |
|---|---|---|
| 1 | Documentazione e `NEXT_STEPS.md` aggiornati allo stato reale | Fatto |
| 2 | `bm25_scores` duplicato in `algorithms.py` | Fatto: rimossa definizione morta, defaults invariati |
| 3 | Docs obsolete su provider/artifact/endpoint | Fatto: `README.md`, `API_CONTRACTS.md` allineati |
| 4 | `accent` salvato ma non applicato | Fatto: applicato a runtime come `--accent` (RGB) |
| 5 | Azioni UI finte | Fatto: toast onesti o dati reali; numeri demo etichettati |
| 6 | Token API non obbligatorio | Fatto: in `production` l'avvio fallisce senza `API_ACCESS_TOKEN` |
| 7 | `DATASET_ALLOWED_ROOTS` troppo largo | Fatto: obbligatorio in `production`, default invariato in dev |
| 8 | Credenziali provider in chiaro | Fatto: cifratura Fernet con `PROVIDER_SETTINGS_KEY` + migrazione automatica |
| 9 | Nodi senza implementazione marcati `completed` | Fatto: ora `failed`; opt-in `allowPassthroughFallback: true` |
| 10 | Bootstrap che degrada in silenzio | Fatto: warning sempre loggato, fail fast in `production` |
| 11 | Persistenza best-effort silenziosa | Fatto: log strutturato; in `production` gli errori propagano |
| 12 | Custom node con id sconosciuto restituiva il primo nodo | Fatto: 404 in tutti gli endpoint; rimosso fallback anche nello store |

Test nuovi: `test_postmerge_security.py` (8), `test_postmerge_resilience.py` (8), `test_postmerge_correctness.py` (11), più aggiornamento di `test_execution_engine.py`.

## Cambiamenti che richiedono attenzione in produzione

Con `APP_ENV=production` il backend ora si rifiuta di partire se mancano `API_ACCESS_TOKEN` o `DATASET_ALLOWED_ROOTS`. È una rottura intenzionale: meglio un avvio fallito che una API non autenticata. Per cifrare `provider_settings.json` serve `PROVIDER_SETTINGS_KEY`; senza chiave il comportamento resta quello storico con un warning.

## Prossimi passi — Wave 2 (funzionalità ancora finte)

1. `POST /models/{id}/test` ritorna output fisso e `latencyMs=142` → usare resolver/hooks reali, `perf_counter`, usage del provider e `estimate_cost`.
2. `POST /evaluations/run` crea un record con score uguale a threshold → calcolare metriche reali con `evaluate_retrieval`/`evaluate_answer`.
3. `/experiments/compare` e `/promote` sono grezzi → calcolare differenze da risultati reali e rendere la promozione persistente.
4. `GET/PATCH /settings/workspace` vive in un dict con lock → persistenza su DB o file atomico.
5. Custom node: test/publish usano risposte seedate e non esiste un runtime isolato → implementare un runner isolato oppure dichiarare esplicitamente 501.
6. Task Celery `execute_pipeline`/`execute_node` ritornano `not_implemented` ma `docker-compose.yml` avvia il worker → implementare o rimuovere il servizio.
7. `peakMemoryMb=0` e token/cost sintetici → misurare memoria e usare l'usage reale dei provider.

## Prossimi passi — Wave 3 (qualità e delivery)

8. CI GitHub Actions: `pytest`, `tsc -b`, `npm run build` su ogni PR.
9. Script `lint` definito ma ESLint non installato → aggiungere dipendenza e config, o rimuovere lo script.
10. Nessun test frontend → Vitest su `portCompatibility`, `settings.api`, `usePipelineStore`.
11. Mock adapter incompleto (`/health`, `/settings/*`, `/providers/*`, PATCH modelli) e valida/run che ignorano il grafo inviato.
12. `TechniquesPage` filtra 552 tecniche nel browser → usare i query params già esposti dal backend.
13. Bundle >4,7 MB → lazy loading delle route e import dinamico di Monaco.
14. Smoke reale di `pl_real_rag` su `ds_133ebd5c` con Ollama/HF/OpenAI: richiede modelli o credenziali, i test usano fake provider.

## Decisioni ancora aperte

- Confermare che la produzione debba avere auth obbligatoria (già implementata in questa ipotesi).
- Scegliere se custodire `PROVIDER_SETTINGS_KEY` in secret manager o keyring OS.
- Trasformare in reali le feature demo di Wave 2 oppure dichiararle come tali in UI/contratti.
