# Guida all'avvio — RAG STUDIO

Questa guida spiega come avviare **frontend** e **backend** nello stato attuale del progetto e come collegarli tra loro.

## Stato attuale (importante)
- **Frontend** (`frontend/`): applicazione React + TypeScript + Vite completa a livello UI (tutte le schermate principali). La configurazione in `frontend/.env` punta al **backend reale** (`VITE_USE_MOCKS=false`, `VITE_API_URL=/api/v1`). Per tornare ai dati simulati nel browser basta impostare `VITE_USE_MOCKS=true` in `frontend/.env.local`.
- **Backend** (`backend/`): API FastAPI (`/api/v1`) con contratti compatibili con il frontend, engine/registry/contratti di dominio e **store in-memory** lato server (dati seed + mutazioni base). L'esecuzione delle pipeline è **reale in-process**: la SSE esegue il DAG tramite nodi reference registrati (chunking, embeddings deterministici, indice vettoriale, retrieval, reranking, generazione) e produce risultati/artefatti ispezionabili. L'executor applica timeout/retry e propaga la cancellazione ai nodi. Le varianti algoritmiche sono funzioni pure condivise tra runtime, confronto ed export, e si selezionano dai parametri dei nodi. Con `PERSISTENCE_BACKEND=database`, pipeline, esecuzioni, risultati e riferimenti artifact sono persistiti su DB e usati come source-of-truth. Con `ARTIFACT_STORE_BACKEND=filesystem` anche il contenuto degli artifact è durevole su disco (retention configurabile); lo stream è idempotente anche tra worker con `STREAM_COORDINATION_BACKEND=redis`. Queste infrastrutture restano **opt-in**: i default sono `memory` e il percorso principale non le richiede (scelta registrata in `DECISIONS.md`). **Non** sono ancora attivi worker Celery, provider/modelli esterni o runtime custom-node isolato.
- Di conseguenza: in modalità `memory` i dati applicativi si resettano al riavvio del backend; in modalità `database` pipeline, esecuzioni, risultati e refs artifact sopravvivono al riavvio, mentre il contenuto degli artifact resta in-memory finché MinIO non viene attivato. I modelli sono comunque reference/deterministici, ma il percorso di esecuzione e i risultati sono reali.

## Prerequisiti
- **Node.js** (consigliato LTS recente) + **npm**
- **Python 3.12+**
- (Opzionale) **Docker + Docker Compose** per l'infrastruttura completa definita in `backend/docker-compose.yml` (PostgreSQL, Redis, MinIO, ecc.) — **non necessaria** per l'avvio dell'API nello stato attuale.

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

# Il file .env è già presente con i default "memory": nessun servizio esterno richiesto
```

Avvia il server (da `backend/`, con venv attivo):

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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

### Docker (infrastruttura/app — opzionale)
Da `backend/`:

```powershell
docker compose up --build
```

> Nello stato attuale l'API può funzionare senza Postgres/Redis/MinIO grazie allo store in-memory; la composizione Docker è predisposta per le fasi successive (persistenza, code, worker, artifact storage).

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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
3. Dai un nome, indica il percorso/URL, ed eventualmente i dettagli di connessione in JSON. La dipendenza `pypdf` è inclusa in `pyproject.toml`: i PDF di testo vengono estratti senza configurazione aggiuntiva, ma solo quando esegui la pipeline (non durante Sync).
   - S3: `{"endpoint":"...","accessKey":"...","secretKey":"...","bucket":"...","prefix":"","secure":true}` (default da `s3://bucket/prefix`);
   - REST API / Notion / Google Drive / Web crawl: `{"headers":{"Authorization":"Bearer ..."}}`, il corpo può essere JSON o testo;
   - PostgreSQL: `{"dsn":"postgresql+psycopg://user@pass@host/db","query":"SELECT id, title, source, content FROM documents LIMIT 200"}`.
4. Sposta i file veri nella cartella indicata (o nel bucket/URL del connettore). Non c'è più nessun import da UI: incollare testo o "caricare file" non aggiungeva i file reali alla sorgente.
5. Premi **Sync dal connettore**: è una scansione di metadati (nome, tipo, dimensione, `indexed`/`skip`) e non estrae testo, quindi è veloce anche con centinaia di PDF. Per `Local files` e `S3` vengono elencati i file senza scaricarne il contenuto; per gli altri connettori l'inventario è derivato dai record ricevuti. I file senza testo estraibile, come le immagini, restano in elenco come `skip`. Il testo viene letto solo quando il nodo *Document source* esegue la pipeline (max 200 documenti). La pagina mostra solo statistiche dei file (tipi, dimensioni, stato): **non crea chunk**. La strategia e la dimensione dei chunk si scelgono nel nodo *Semantic chunking* della pipeline, così ogni pipeline può usare la propria.
6. Apri l'editor di una pipeline, seleziona il nodo **Document source** e scegli il dataset dal parametro **Dataset**: la pipeline userà quei documenti (chunking semantico, retrieval, reranking e generazione inclusi). I parametri successivi filtrano cosa passa davvero nel ramo:
   - **File types**: `all` (default), `pdf`, `text` (txt/md), `txt`, `md`, `json`, `jsonl`, `csv`, `documents` (tutti i tipi supportati) oppure `other`;
   - **File name contains**: sottostringa nel titolo o nel percorso, con wildcard `*` (per esempio `eni_*`).

### Pipeline ibride (PDF e testo su rami diversi)

1. Apri una pipeline e aggiungi **due** nodi *Document source* sullo stesso dataset.
2. Imposta il primo con `File types = pdf` e il secondo con `File types = text`; in alternativa usa **File name contains** per separare per nome. I due parametri si possono combinare nello stesso nodo.
3. Aggiungi il nodo **Merge documents** (categoria *Document Processing*) e collega i due sorgenti alle porte `in_documents_a` e `in_documents_b`. Il merge deduplica per id.
4. Collega l'uscita `documents` del merge al solito **Semantic chunking**, poi embedding, vettore, retrieval, reranking e generazione. Ora puoi mettere trasformazioni diverse prima del merge, per esempio un parser diverso sul ramo PDF.

Se un dataset contiene solo PDF, il ramo `text` resta vuoto: è normale, controlla l'inventario nella pagina Datasets prima di collegare i rami.

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

Lo script generato usa solo la libreria standard di Python; la configurazione algoritmica viene letta dal grafo della pipeline salvato nel backend.

---

## Risoluzione problemi comuni
- **`npm install` fallisce**: verifica versione Node/npm e riprova; elimina `node_modules` e `package-lock.json` solo se necessario.
- **Errori import/dipendenze Python**: assicurati che il venv sia attivo e che `pip install -e .[dev]` sia completato senza errori.
- **Porta occupata**: cambia porta (`--port 8000` per Uvicorn, `--port` per Vite) e allinea proxy/URL.
- **Frontend non vede il backend**: controlla che `VITE_USE_MOCKS=false`, che il backend risponda su `/api/v1/system/status`, che il proxy Vite punti al target corretto e riavvia il dev server dopo modifiche a `.env`.
- **Dati che "spariscono"**: previsto con store in-memory (riavvio backend) e, in mock mode, secondo il comportamento dell'adapter in-browser. In modalità `database` pipeline, esecuzioni, risultati e refs artifact sono persistenti; il contenuto degli artifact resta in-memory finché non si configura MinIO.
