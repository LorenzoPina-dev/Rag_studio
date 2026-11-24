# Guida all'avvio — RAG STUDIO

Questa guida spiega come avviare **frontend** e **backend** nello stato attuale del progetto e come collegarli tra loro.

## Stato attuale (importante)
- **Frontend** (`frontend/`): applicazione React + TypeScript + Vite completa a livello UI (tutte le schermate principali). La configurazione in `frontend/.env` punta al **backend reale** (`VITE_USE_MOCKS=false`, `VITE_API_URL=/api/v1`). Per tornare ai dati simulati nel browser basta impostare `VITE_USE_MOCKS=true` in `frontend/.env.local`.
- **Backend** (`backend/`): API FastAPI (`/api/v1`) con contratti compatibili con il frontend, engine/registry/contratti di dominio e store lato server. L'esecuzione delle pipeline è **reale in-process**: la SSE esegue il DAG e produce risultati/artefatti ispezionabili. Oltre ai nodi deterministici (`pl_hybrid_rag`) è presente **`pl_real_rag`**, la pipeline dimostrativa che usa **provider reali Hugging Face, Ollama e OpenAI** per embedding, reranking e generazione. L'executor applica timeout/retry e propaga la cancellazione ai nodi. Le varianti algoritmiche sono funzioni pure condivise tra runtime, confronto ed export. Con `PERSISTENCE_BACKEND=database`, pipeline, esecuzioni, risultati e riferimenti artifact sono persistiti su DB; con `ARTIFACT_STORE_BACKEND=filesystem` anche il contenuto degli artifact è durevole su disco. Queste infrastrutture restano **opt-in** (default `memory`); i worker Celery e il runtime custom-node isolato non sono ancora operativi.
- Di conseguenza: in modalità `memory` i dati applicativi si resettano al riavvio del backend; in modalità `database` pipeline, esecuzioni, risultati e refs artifact sopravvivono al riavvio. I risultati sono reali: con `pl_real_rag` e almeno un provider configurato, embedding/reranking/generazione arrivano dai modelli scelti, non da euristiche.

## Prerequisiti
- **Node.js** (consigliato LTS recente) + **npm**
- **Python 3.12+**
- (Opzionale) **Docker + Docker Compose** per i tool usati dalle pipeline (`progetti/docker-compose.yml`: Qdrant, Neo4j; `backend/docker-compose.yml`: PostgreSQL, Redis, MinIO) — **non necessari** per l'avvio dell'API in memoria. Backend e frontend restano sempre locali, avviati dalle rispettive cartelle del progetto.

> Nota: `backend/pyproject.toml` dichiara dipendenze anche per DB/queue/storage/observability (SQLAlchemy, Celery, Redis, MinIO, OpenTelemetry, ecc.). Per l'esecuzione dell'API in-memory attuale sono sufficienti le dipendenze web/core (FastAPI, Uvicorn, Pydantic, ecc.), ma l'installazione completa `pip install -e .` è la strada più semplice.

---

## 1) Avvio del backend (FastAPI)

Apri un terminale nella cartella `backend`:

```powershell
cd backend

# Crea e attiva un virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# (CMD: .venv\Scripts\activate.bat)

# Installa le dipendenze
pip install -e .[dev]
# oppure solo runtime: pip install -e .

# Copia .env.example in .env se vuoi configurare provider/token (nessuna chiave reale nel repo)
```

Avvia il server (da `backend/`, con venv attivo), in ascolto solo su loopback:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> **Non esporre la API in rete senza `API_ACCESS_TOKEN`.** Impostalo in `backend/.env`: quando è presente, tutte le richieste mutanti (`POST`/`PATCH`/`PUT`/`DELETE`) devono inviare l'header `X-API-Token` con lo stesso valore. `GET`, `/health`, `/docs` e `/openapi.json` restano pubblici. Senza token il comportamento è invariato (sviluppo locale e test).

Endpoint utili:
- **Health**: `http://localhost:8000/health`
- **Stato sistema (API v1)**: `http://localhost:8000/api/v1/system/status`
- **OpenAPI/Swagger**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Test backend
Da `backend/` (venv attivo):

```powershell
pytest -q
```

### Provider reali (pl_real_rag)

La pipeline `pl_real_rag` usa i provider reali; per vederla agire dal frontend tieni `VITE_USE_MOCKS=false` (configurazione attuale). I provider si configurano da **Settings → Providers** (`PATCH /api/v1/providers/settings`) oppure via variabili d'ambiente in `backend/.env`:

- **Ollama** (embedding + generazione locali): avvia il runtime con `ollama serve`, poi scarica i modelli con `ollama pull nomic-embed-text` e `ollama pull llama3.2:1b`. Imposta `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) se il runtime non è locale. Lo stato si legge da `GET /api/v1/providers/status`.
- **Hugging Face** (embedding, reranking e generazione locali): sono sufficienti le dipendenze dichiarate (`sentence-transformers`, `transformers`). I modelli predefiniti sono `BAAI/bge-small-en-v1.5`, `cross-encoder/ms-marco-MiniLM-L-6-v2` e `google/flan-t5-small`; personalizzali con `HF_EMBEDDING_MODEL`, `HF_RERANKER_MODEL`, `HF_GENERATOR_MODEL`. Il download automatico è controllato da `allow_model_download`.
- **OpenAI**: imposta `OPENAI_API_KEY` (oppure salva la chiave solo nel file locale `backend/data/provider_settings.json`, mai nel codice o nelle risposte API). `OPENAI_BASE_URL` è opzionale per endpoint compatibili. Non inserire chiavi reali in `.env.example`, nei test o nella documentazione.

Se un provider non è raggiungibile la pipeline segnala l'errore: non c'è fallback silenzioso a embedding hash per i provider reali. Le impostazioni workspace (nome, regione, concorrenza, notifiche, flag) sono disponibili via `GET`/`PATCH /api/v1/settings/workspace`; sono in memoria e non richiedono persistenza su disco.

### Docker (solo tool — opzionale)
I tool delle pipeline ESG girano in Docker, ma **API e UI restano locali**. Dalla root del progetto:

```powershell
cd progetti
docker compose up -d --build
```

Qdrant e Neo4j sono pubblicati su `localhost:6333` e `localhost:7474`; il backend locale li raggiunge con `target=localhost`/`host=127.0.0.1`. I PDF restano in `Data\` e vengono letti direttamente dal backend locale, senza mount o riscritture dentro i container. Vedi `progetti/README.md` per i dettagli.

> Nello stato attuale l'API può funzionare senza Postgres/Redis/MinIO grazie allo store in-memory; `backend/docker-compose.yml` resta disponibile solo come infrastruttura opzionale, non per avviare il backend.

---

## 2) Avvio del frontend (Vite + React)

Apri un **secondo** terminale nella cartella `frontend`:

```powershell
cd frontend
npm install
npm run dev
```

- URL di sviluppo: **http://localhost:5173** (Vite configurato con `--host 0.0.0.0 --port 5173`)
- Build produzione: `npm run build`
- Anteprima build: `npm run preview` (porta 4173)

### Collegamento al backend reale (configurazione attuale)
`frontend/.env` è già impostata senza mock:

```env
VITE_USE_MOCKS=false
VITE_API_URL=/api/v1
VITE_API_PROXY=http://localhost:8000
```

Avvia il backend su `http://localhost:8000` (vedi sopra), poi `npm run dev`. Il proxy di Vite inoltra le richieste `/api` a `VITE_API_PROXY`.

### Modalità mock (opzionale)
Per usare i dati simulati in-browser senza backend, crea `frontend/.env.local`:

```env
VITE_USE_MOCKS=true
```

`.env.local` ha priorità su `.env`; riavvia il dev server dopo la modifica.

Note:
- `frontend/vite.config.ts` include un proxy dev: le richieste verso `/api` vengono inoltrate a `http://localhost:8000` (configurabile con `VITE_API_PROXY`). Con `VITE_API_URL=/api/v1` il frontend chiamerà il backend locale tramite proxy.
- In alternativa puoi puntare direttamente all'URL del backend, ad esempio `VITE_API_URL=http://localhost:8000/api/v1` (richiede CORS abilitato sul backend, già previsto per `http://localhost:5173`).

---

## 3) Avvio rapido (due terminali)

**Terminale 1 — backend**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminale 2 — frontend**
```powershell
cd frontend
npm run dev
```

- UI contro API backend (configurazione attuale): avvia backend e frontend, poi apri `http://localhost:5173`.
- Solo UI con dati mock: crea `frontend/.env.local` con `VITE_USE_MOCKS=true` e riavvia il dev server.

---

## 4) Dove mettere i dati

I dataset sono ora dati di progetto veri, non metadati dimostrativi. Vengono salvati in `backend/data/datasets.json` e sono la sorgente dei documenti per esecuzioni, confronto ed export.

### Dalla pagina Datasets (consigliato)

1. Apri **Datasets** e clicca **New dataset**.
2. Scegli il connettore tra `Local files`, `S3`, `Notion`, `Google Drive`, `Web crawl`, `PostgreSQL`, `REST API`.
3. Dai un nome, indica il percorso/URL, ed eventualmente i dettagli di connessione in JSON. Le dipendenze `pymupdf` e `pypdf` sono incluse in `pyproject.toml`: i PDF vengono estratti senza configurazione aggiuntiva, ma solo quando esegui la pipeline (non durante Sync). PyMuPDF recupera anche tabelle, immagini e grafici; `pypdf` resta come fallback testuale.
   - S3: `{"endpoint":"...","accessKey":"...","secretKey":"...","bucket":"...","prefix":"","secure":true}` (default da `s3://bucket/prefix`);
   - REST API / Notion / Google Drive / Web crawl: `{"headers":{"Authorization":"Bearer ..."}}`, il corpo può essere JSON o testo;
   - PostgreSQL: `{"dsn":"postgresql+psycopg://user@pass@host/db","query":"SELECT id, title, source, content FROM documents LIMIT 200"}`.
   Le chiavi sensibili (`secretKey`, `password`, `dsn`, `token`, `apiKey`, `accessKey`, `secret`, `authorization`, `headers.Authorization`) sono sostituite con `***` in tutte le risposte dataset: il valore reale resta solo nel file locale e viene usato a runtime. I percorsi `Local files` devono stare sotto `DATASET_ALLOWED_ROOTS` (default: root del repository e cartella temp); i file di configurazione come `provider_settings.json` non sono mai ingestibili. I connettori HTTP bloccano IP privati/loopback/link-local e rivalidano ogni redirect (max 3), inoltrando gli header solo allo stesso host/porta.
4. Sposta i file veri nella cartella indicata (o nel bucket/URL del connettore). Non c'è più nessun import da UI: incollare testo o "caricare file" non aggiungeva i file reali alla sorgente.
5. Premi **Sync dal connettore**: è una scansione di metadati (nome, tipo, dimensione, `indexed`/`skip`) e non estrae testo, quindi è veloce anche con centinaia di PDF. Per `Local files` e `S3` vengono elencati i file senza scaricarne il contenuto; per gli altri connettori l'inventario è derivato dai record ricevuti. I file senza testo estraibile, come le immagini, restano in elenco come `skip`. Il testo viene letto solo quando il nodo *Document source* esegue la pipeline (max 200 documenti). La pagina mostra solo statistiche dei file (tipi, dimensioni, stato): **non crea chunk**. La strategia e la dimensione dei chunk si scelgono nel nodo *Semantic chunking* della pipeline, così ogni pipeline può usare la propria. `POST /api/v1/datasets/sync` esegue davvero la sincronizzazione di tutti i dataset e restituisce `synced`, `failed` e `syncedAt`: un singolo connettore in errore non blocca gli altri.
6. Apri l'editor di una pipeline, seleziona il nodo **Document source** e scegli il dataset dal parametro **Dataset**: la pipeline userà quei documenti (chunking semantico, retrieval, reranking e generazione inclusi). I parametri successivi filtrano cosa passa davvero nel ramo:
   - **File types**: `all` (default), `pdf`, `text` (txt/md), `txt`, `md`, `json`, `jsonl`, `csv`, `documents` (tutti i tipi supportati) oppure `other`;
   - **File name contains**: sottostringa nel titolo o nel percorso, con wildcard `*` (per esempio `eni_*`).

### Pipeline ibride (PDF e testo su rami diversi)

1. Apri una pipeline e aggiungi **due** nodi *Document source* sullo stesso dataset.
2. Imposta il primo con `File types = pdf` e il secondo con `File types = text`; in alternativa usa **File name contains** per separare per nome. I due parametri si possono combinare nello stesso nodo.
3. Aggiungi il nodo **Merge documents** (categoria *Document Processing*) e collega i due sorgenti alle porte `in_documents_a` e `in_documents_b`. Il merge deduplica per id.
4. Collega l'uscita `documents` del merge al solito **Semantic chunking**, poi embedding, vettore, retrieval, reranking e generazione. Ora puoi mettere trasformazioni diverse prima del merge, per esempio un parser diverso sul ramo PDF.

Se un dataset contiene solo PDF, il ramo `text` resta vuoto: è normale, controlla l'inventario nella pagina Datasets prima di collegare i rami.

### Estrazione di tabelle, immagini e grafici dai PDF

Il nodo **Document component extraction** (categoria *Document Processing*) arricchisce i documenti PDF: estrae testo, tabelle (anche in Markdown), immagini incorporate e grafici vettoriali, ne ricava didascalie/etichette e unisce il risultato al testo. Collega l'uscita `documents` di un *Document source* all'ingresso `Documents` del nodo, poi prosegui con *Semantic chunking*.

- `Extract tables`, `Extract images`, `Extract charts / figures` abilitano le singole estrazioni; `Merge into document text` controlla l'unione nel testo.
- `Visual description`: `reference` (default) genera descrizioni deterministiche da didascalie, etichette e geometria, senza chiamare modelli; `openai` o `ollama` usano un modello visione reale (serve la chiave OpenAI o un runtime Ollama con un modello visione); `off` disattiva le descrizioni. `Vision model` vuoto usa `OPENAI_VISION_MODEL` o `OLLAMA_VISION_MODEL` (default `gpt-4o-mini` e `llava`).
- Le immagini e i grafici estratti sono salvati anche come artifact dell'esecuzione. L'uscita `Components` contiene i componenti strutturati senza i dati binari grezzi.

Le stesse chiavi (`fileTypes`, `fileName`) valgono per `/comparison/run` e per l'export Python: lo script generato applica gli stessi filtri e include i soli documenti selezionati.

### Da file

`backend/data/documents.json` resta il corpus predefinito usato quando il nodo *Document source* non ha un dataset selezionato: è un array con `id`, `title`, `source`, `content`. Il file si legge a ogni richiesta, quindi non serve riavviare il backend. `backend/data/datasets.json` contiene invece i dataset creati dalla UI, con il solo inventario dei file: il testo dei documenti non viene copiato lì, ma letto dal connettore a ogni esecuzione.

- Se `documents.json` manca, si usa il corpus dimostrativo di `backend/app/components/algorithms.py` (`DEFAULT_CORPUS`).
- Se un JSON è malformato o manca un campo, la risposta segnala l'errore con il numero del documento problematico.
- Per spostare i file, decommenta `RAG_DATASET_PATH` in `backend/.env` e indica un percorso assoluto: `datasets.json` verrà creato nella stessa cartella.
- La lista `GET /api/v1/datasets` è leggera (pochi KB) perché non trasporta il testo: i dataset con connettore hanno `items: []` e solo l'inventario `files`. I selettori usano `GET /api/v1/datasets/options`.
- I PDF scansionati senza testo danno un errore esplicito quando la pipeline prova a leggerli: serve OCR, non previsto in questa versione.

---

## 5) Confrontare algoritmi ed esportare Python

Questa parte serve allo scopo principale del progetto: vedere cosa cambia cambiando algoritmo e portare via il codice. Funziona con il backend in memoria, senza Postgres/Redis/MinIO.

### Dal frontend (backend reale)

1. Avvia backend e frontend come sopra, con `VITE_USE_MOCKS=false`.
2. Apri **Experiments** → sezione **“Confronta varianti RAG”**.
3. Seleziona il **Dataset** da usare (default: corpus di `documents.json`) e scrivi la query (es. `What is BM25?`).
4. Scegli almeno due preset tra:
   - `Hybrid + extractive` (baseline);
   - `BM25 + concise` (solo lessicale, risposta di una frase);
   - `Dense + diversity` (solo vettoriale, reranking per diversità).
5. Clicca **Run comparison**: vedi risposta, fonti, metriche e durata affiancate.
6. Nell'editor di una pipeline clicca **Export .py** (o *Export Python script* dal menu in alto) per scaricare lo script standalone.

In mock mode la sezione mostra risultati segnaposto e l'export `.py` è un file dimostrativo: per risultati ed export reali serve `VITE_USE_MOCKS=false`.

### Da riga di comando

Confronto (stessa query, due varianti):

```powershell
curl -X POST http://localhost:8000/api/v1/comparison/run `
  -H "Content-Type: application/json" `
  -d '{"query":"What is BM25?","datasetId":"ds_product_docs","variants":[{"id":"a","label":"Hybrid","config":{}},{"id":"b","label":"BM25 concise","config":{"retrievalAlgorithm":"bm25","generationStrategy":"concise"}}]}'
```

Export ed esecuzione dello script:

```powershell
curl "http://localhost:8000/api/v1/pipelines/pl_hybrid_rag/export?format=python&query=What%20is%20BM25%3F" -o pipeline.py
python pipeline.py "What is BM25?"
python pipeline.py "What is BM25?" --json
```

L'export è **dual-mode**: per le pipeline deterministiche lo script usa solo la libreria standard Python; per `pl_real_rag` include `PROVIDER_CONFIG` e richiama il layer provider di RAG Studio (Hugging Face/Ollama/OpenAI), senza embedded di chiavi. La configurazione algoritmica viene letta dal grafo della pipeline salvato nel backend.

---

## Risoluzione problemi comuni
- **`npm install` fallisce**: verifica versione Node/npm e riprova; elimina `node_modules` e `package-lock.json` solo se necessario.
- **Errori import/dipendenze Python**: assicurati che il venv sia attivo e che `pip install -e .[dev]` sia completato senza errori.
- **Porta occupata**: cambia porta (`--port 8000` per Uvicorn, `--port` per Vite) e allinea proxy/URL.
- **Frontend non vede il backend**: controlla che `VITE_USE_MOCKS=false`, che il backend risponda su `/api/v1/system/status`, che il proxy Vite punti al target corretto e riavvia il dev server dopo modifiche a `.env`.
- **Dati che "spariscono"**: previsto con store in-memory (riavvio backend) e, in mock mode, secondo il comportamento dell'adapter in-browser. In modalità `database` pipeline, esecuzioni, risultati e refs artifact sono persistenti; il contenuto degli artifact resta in-memory finché non si configura MinIO.
