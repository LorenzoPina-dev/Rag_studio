# Audit fixes — stato e prossimi passi

Branch: `fix/audit-hardening` (worktree `D:\github\Rag_studio-audit-fix`)
Baseline: `43204e2` (`main`, commit iniziale). Nessun push eseguito.

## Verifiche dopo le fix

- `cd backend && python -m pytest -q` → **129 passed** (94 iniziali + 35 nuovi).
- `cd frontend && npx tsc -b --pretty false` → OK.
- `cd frontend && npm run build` → OK.

## Cosa è stato corretto

| # | Finding | Stato |
|---|---------|-------|
| 1 | Confronto multi-variante sovrascriveva il corpus e ignorava i provider | Corretto: corpus immutabile per dataset, `datasetId` dalla pipeline, hook reali |
| 2 | `retrievalAlgorithm` forzato a `hybrid` | Corretto: parametro usato nel calcolo e nei metadati |
| 3 | API mutanti senza auth, `debug=True`, bind `0.0.0.0` | Corretto: `debug=False`, bind loopback nella guida, token opzionale `X-API-Token` |
| 4 | Path traversal Local files e SSRF HTTP | Corretto: root consentite, blocco host privati, redirect rivalidati, header non propagati |
| 5 | Credenziali dataset esposte da `GET /datasets` | Corretto: redazione di `connection` su tutti gli endpoint Dataset |
| 6 | Validate/Run su pipeline salvata, save silenzioso | Corretto: auto-save, `try/catch`, errori SSE gestiti |
| 7 | “Save changes” dei Settings fake | Corretto: `GET/PATCH /settings/workspace` reali e mutation frontend |
| 8 | Default mock `true` | Corretto: default `false`, warning esplicito, `.env.example` frontend |
| 9 | Dipendenze provider non dichiarate | Corretto in `pyproject.toml` |
| 10 | Export perde modelli rerank/generation | Corretto: `rerank_model` e `generation_model` in `PROVIDER_CONFIG` |
| 11 | `alpha` ignorato con RRF | Corretto: pesatura delle due liste, default 0.7 che conserva il ranking storico |
| 12 | MMR senza vettori e con score sintetici | Corretto: `ValueError` esplicito e score MMR reali |
| 13 | `cosineSimilarity` era lo score fused | Corretto: letto da `scores["dense"]`/`cosine`, altrimenti 0 |
| 14 | Porte UI/backend divergenti | Corretto: tipo strong `context` allineato; generation consuma contesto pre-renderito |
| 15 | Evento SSE `error` ignorato | Corretto: toast e pulsante Run riabilitato |
| 16 | Persistenza JSON non atomica | Corretto: scrittura su temp file + `os.replace` |
| 17 | `POST /datasets/sync` finto | Corretto: sincronizza tutti i dataset e riporta successi/fallimenti |
| 18 | Indicatori health finti | Corretto: health check reale (`/api/v1/health` + `/providers/status`), conteggio dataset sani |
| 19 | `NaN%` nei dataset vuoti | Corretto: denominatore 0 gestito |
| 20 | `PATCH /evaluations/settings` senza validazione | Corretto: modello strict, `extra="forbid"`, NaN/Infinity → 422 |
| 21 | `pl_real_rag` assente dal seed DB | Corretto: aggiunto a `_DEMO_IDS` |
| 22 | Documentazione obsoleta | Corretto: guida, roadmap, README e API contracts aggiornati |
| 23 | `.gitignore` mancante | Corretto nel commit baseline |
| 24 | Test mancanti | Aggiunti 35 test mirati (`test_audit_rag_fixes.py`, `test_audit_api_fixes.py`) |
| 25 | HF `CrossEncoder`/`truncation` fissi | Corretto: configurabili, default invariato |
| 26 | `.env.example` frontend/contract export | Corretto: `.env.example` creato, API contracts aggiornati |

## Prossimi passi

1. **GitHub**: il repo è inizializzato solo in locale. Configurare il remote con
   `git remote add origin <URL_REPO_GITHUB>` e fare push di `main` e
   `fix/audit-hardening`. `gh` non è installato in questa macchina.
2. **Sicurezza residua**: `API_ACCESS_TOKEN` è opzionale per non rompere dev/test.
   Prima di esporre il backend in rete impostarlo e restringere
   `DATASET_ALLOWED_ROOTS` alla sola cartella dei dataset (oggi include root repo
   e temp dir per i test). Le credenziali provider restano in chiaro in
   `backend/data/provider_settings.json`: valutare cifratura a riposo.
3. **Smoke reale su questo worktree**: rieseguire `pl_real_rag` su `ds_133ebd5c`
   con `fileName=eni_2025.pdf` per confermare che hook reali, context-builder e
   export funzionino dopo le modifiche (i test usano fake, non modelli veri).
4. **CI**: aggiungere un workflow che esegua `pytest`, `tsc -b` e `npm run build`
   su ogni PR, più un job opzionale con Ollama per lo smoke reale.
5. **Refactoring rimasto**: frontend `frontend/src/api/mock/adapter.ts` non
   implementa ancora `/settings/workspace`, `/providers/status` e `/health`;
   non è il percorso normale (mock disattivato), ma va allineato se si vuole
   supportare di nuovo il mock mode.
6. **Performance**: il bundle frontend supera 4,7 MB (`vite build` avvisa).
   Valutare code splitting delle pagine e del Monaco editor in un branch dedicato.
