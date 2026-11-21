"""Catalogo esaustivo e machine-readable delle tecniche RAG supportate.

Modulo puro: nessuna dipendenza da provider, database o dal modulo
``app.components.advanced_algorithms``. I nomi di implementazione sono solo
metadati che descrivono dove risiede (o risiederà) la logica di riferimento.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

Status = Literal["reference", "provider", "integration", "design"]

STATUSES: tuple[Status, ...] = ("reference", "provider", "integration", "design")
"""Stati supportati: locale deterministico, provider esterno, integrazione, design."""

CATEGORIES: tuple[str, ...] = (
    "Data Sources",
    "Parsing",
    "Preprocessing",
    "Chunking",
    "Enrichment",
    "Embeddings",
    "Indexing & Storage",
    "Query Processing",
    "Retrieval",
    "Fusion",
    "Reranking",
    "Selection & Filtering",
    "Context Processing",
    "Generation",
    "Validation",
    "Orchestration",
    "Evaluation",
    "Monitoring & Security",
)
"""Tassonomia funzionale principale (nomi esatti)."""

PHASES: tuple[str, ...] = (
    "1 Data ingestion",
    "2 Parsing e preprocessing",
    "3 Chunking e document structuring",
    "4 Enrichment e metadata extraction",
    "5 Embedding e indexing",
    "6 Query understanding",
    "7 Retrieval",
    "8 Reranking e filtering",
    "9 Context construction",
    "10 Generation",
    "11 Validation e evaluation",
    "12 Feedback memoria continuous improvement",
    "13 RAG orchestration",
    "14 Security e governance",
    "15 Observability e ottimizzazione operativa",
)
"""Fasi della pipeline RAG (nomi esatti, con numero progressivo)."""


@dataclass(frozen=True, slots=True)
class Technique:
    """Una tecnica RAG con metadati di tassonomia e di implementazione."""

    id: str
    name: str
    category: str
    phase: str
    description: str
    status: Status
    implementation: str | None
    tags: tuple[str, ...]
    parameters: dict[str, str]


class _Row(NamedTuple):
    """Riga compatta usata per definire il catalogo senza ripetere i campi comuni."""

    id: str
    name: str
    description: str
    status: Status
    implementation: str | None
    tags: tuple[str, ...]
    parameters: dict[str, str]


def _parse_parameters(value: str) -> dict[str, str]:
    """Converte ``'k=5 metric=cosine'`` in un dizionario di parametri."""
    result: dict[str, str] = {}
    for token in value.split():
        if "=" in token:
            key, _, item = token.partition("=")
            result[key] = item
    return result


def _t(
    id: str,
    name: str,
    description: str,
    status: Status = "design",
    implementation: str | None = None,
    tags: str = "",
    parameters: str = "",
) -> _Row:
    """Costruisce una riga compatta (tags e parametri come stringhe)."""
    return _Row(
        id=id,
        name=name,
        description=description,
        status=status,
        implementation=implementation,
        tags=tuple(tags.split()),
        parameters=_parse_parameters(parameters),
    )


def _group(category: str, phase: str, rows: tuple[_Row, ...]) -> tuple[Technique, ...]:
    """Assegna categoria e fase a un gruppo di righe."""
    return tuple(
        Technique(
            id=row.id,
            name=row.name,
            category=category,
            phase=phase,
            description=row.description,
            status=row.status,
            implementation=row.implementation,
            tags=row.tags,
            parameters=row.parameters,
        )
        for row in rows
    )


def _slug(value: str) -> str:
    """Normalizza un nome in slug minuscolo con trattini."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower().replace("&", " ")).strip("-")


def category_slug(category: str) -> str:
    """Slug stabile di una categoria (es. ``Indexing & Storage`` -> ``indexing-storage``)."""
    return _slug(category)


def phase_slug(phase: str) -> str:
    """Slug stabile di una fase, senza il numero iniziale."""
    return _slug(phase.split(" ", 1)[-1])


_DATA_SOURCES = _group(
    "Data Sources",
    PHASES[0],
    (
        _t("local-files", "Local Files", "Carica documenti da una cartella locale.", "integration", tags="filesystem batch", parameters="path=. recursive=true"),
        _t("s3-connector", "Amazon S3 Connector", "Sincronizza documenti da bucket S3.", "integration", tags="cloud aws", parameters="bucket= region=us-east-1"),
        _t("gcs-connector", "Google Cloud Storage", "Legge oggetti da Google Cloud Storage.", "integration", tags="cloud gcp"),
        _t("azure-blob-connector", "Azure Blob Storage", "Ingestione da container Azure Blob.", "integration", tags="cloud azure"),
        _t("notion-connector", "Notion", "Importa pagine e database Notion.", "integration", tags="saas wiki"),
        _t("confluence-connector", "Confluence", "Importa spazi e pagine Confluence.", "integration", tags="saas wiki"),
        _t("google-drive-connector", "Google Drive", "Sincronizza file da Google Drive.", "integration", tags="saas drive"),
        _t("sharepoint-connector", "SharePoint", "Importa documenti da siti SharePoint.", "integration", tags="saas microsoft"),
        _t("web-crawler", "Web Crawler", "Crawl ricorsivo di pagine web pubbliche.", "integration", tags="web crawl", parameters="depth=2 robots=true"),
        _t("sitemap-ingestion", "Sitemap Ingestion", "Ingestione degli URL da sitemap XML.", "integration", tags="web sitemap"),
        _t("rest-api-source", "REST API Source", "Recupera record da endpoint REST.", "integration", tags="api http", parameters="method=GET page_size=100"),
        _t("graphql-source", "GraphQL Source", "Interroga API GraphQL con query configurabili.", "integration", tags="api graphql"),
        _t("postgresql-source", "PostgreSQL Source", "Legge tabelle e viste da PostgreSQL.", "integration", tags="database sql"),
        _t("mysql-source", "MySQL Source", "Legge tabelle da database MySQL.", "integration", tags="database sql"),
        _t("mongodb-source", "MongoDB Source", "Esporta collezioni MongoDB come documenti.", "integration", tags="database nosql"),
        _t("elasticsearch-source", "Elasticsearch Source", "Importa documenti indicizzati in Elasticsearch.", "integration", tags="search database"),
        _t("slack-source", "Slack Export", "Importa canali e messaggi Slack.", "integration", tags="saas chat"),
        _t("github-source", "GitHub Source", "Importa repository, issue e README.", "integration", tags="saas code"),
        _t("jira-source", "Jira Source", "Importa ticket e commenti Jira.", "integration", tags="saas issues"),
        _t("email-source", "Email / IMAP", "Importa email da server IMAP.", "integration", tags="email imap"),
        _t("pdf-upload", "PDF Upload", "Carica file PDF tramite upload utente.", "integration", tags="upload pdf"),
        _t("youtube-transcript", "YouTube Transcript", "Recupera trascrizioni di video YouTube.", "provider", tags="video transcript"),
        _t("rss-feed", "RSS Feed", "Legge articoli da feed RSS/Atom.", "integration", tags="web feed"),
        _t("ocr-scan-source", "Scanned Documents", "Acquisisce documenti scansionati da trattare con OCR.", "integration", tags="scan ocr"),
        _t("database-cdc", "Database CDC", "Cattura modifiche incrementali da log del database.", "integration", tags="database streaming"),
        _t("manual-text-source", "Manual Text Input", "Inserisce testo grezzo direttamente nella pipeline.", "reference", "text_input", "manual text"),
        _t("signed-url-source", "Signed URL Fetch", "Scarica documenti da URL firmati temporaneamente.", "integration", tags="http security"),
        _t("incremental-sync", "Incremental Sync", "Sincronizza solo i documenti modificati dopo l'ultima corsa.", "integration", tags="sync delta"),
    ),
)

_PARSING = _group(
    "Parsing",
    PHASES[1],
    (
        _t("pdf-pypdf", "PDF Parsing (pypdf)", "Estrae testo e metadati dai PDF con pypdf.", "integration", "parse_pdf", "pdf pypdf"),
        _t("pdf-layout-analysis", "PDF Layout Analysis", "Ricostruisce colonne, paragrafi e blocchi visivi.", "provider", tags="pdf layout"),
        _t("ocr-tesseract", "OCR Tesseract", "Riconosce testo da immagini e PDF scansionati.", "integration", "ocr_document", "ocr tesseract", "lang=ita"),
        _t("table-extraction", "Table Extraction", "Riconosce tabelle e le converte in strutture dati.", "provider", tags="table structure"),
        _t("html-parsing", "HTML Parsing", "Estrae testo e link da documenti HTML.", "reference", "parse_html", "html web"),
        _t("markdown-parsing", "Markdown Parsing", "Parsa titoli, liste e blocchi Markdown.", "reference", "parse_markdown", "markdown structure"),
        _t("docx-parsing", "DOCX Parsing", "Estrae paragrafi e tabelle da file Word.", "integration", tags="office docx"),
        _t("xlsx-parsing", "XLSX Parsing", "Converte fogli elettronici in righe testuali.", "integration", tags="office excel table"),
        _t("pptx-parsing", "PPTX Parsing", "Estrae slide, titoli e note da PowerPoint.", "integration", tags="office pptx"),
        _t("epub-parsing", "EPUB Parsing", "Estrae capitoli da pubblicazioni EPUB.", "integration", tags="ebook epub"),
        _t("code-ast-parsing", "Code AST Parsing", "Analizza file sorgente tramite albero sintattico.", "integration", tags="code ast"),
        _t("image-captioning", "Image Captioning", "Genera descrizioni testuali di immagini con un VLM.", "provider", tags="image vision caption"),
        _t("audio-asr", "Audio ASR", "Trascrive audio in testo con riconoscimento vocale.", "provider", tags="audio speech"),
        _t("video-frame-extraction", "Video Frame Extraction", "Campiona fotogrammi di video per l'analisi visiva.", "integration", tags="video frames"),
        _t("latex-parsing", "LaTeX Parsing", "Converte sorgenti LaTeX in testo strutturato.", "integration", tags="latex academic"),
        _t("email-parsing", "Email Parsing", "Separa header, mittente, corpo e allegati.", "reference", "parse_email", "email mime"),
        _t("json-structure-parsing", "JSON Parsing", "Appiattisce documenti JSON mantenendo i percorsi.", "reference", "parse_json", "json structured"),
        _t("csv-parsing", "CSV Parsing", "Legge file CSV con rilevamento del delimitatore.", "reference", "parse_csv", "csv table"),
        _t("xml-parsing", "XML Parsing", "Estrae nodi testuali da documenti XML.", "reference", "parse_xml", "xml structured"),
        _t("boilerplate-detection", "Boilerplate Detection", "Rimuove menu, banner e testo non informativo.", "design", tags="cleaning web"),
        _t("header-footer-removal", "Header / Footer Removal", "Elimina intestazioni e piè di pagina ricorrenti.", "reference", "remove_headers", "pdf cleaning"),
        _t("reading-order-reconstruction", "Reading Order Reconstruction", "Riordina i blocchi secondo l'ordine di lettura.", "design", tags="layout document"),
        _t("multi-column-parsing", "Multi-column Parsing", "Gestisce documenti con colonne multiple.", "design", tags="layout pdf"),
        _t("figure-extraction", "Figure Extraction", "Estrae immagini e didascalie dai documenti.", "integration", tags="image figure"),
        _t("footnote-extraction", "Footnote Extraction", "Separa note a piè di pagina dal testo principale.", "design", tags="pdf academic"),
        _t("hyperlink-preservation", "Hyperlink Preservation", "Conserva gli URL come metadati di provenienza.", "reference", "preserve_links", "html links"),
        _t("encoding-detection", "Encoding Detection", "Rileva la codifica dei caratteri del sorgente.", "reference", "detect_encoding", "text encoding"),
        _t("mime-detection", "MIME Detection", "Classifica il tipo di file prima del parsing.", "reference", "detect_mime", "file type"),
        _t("page-splitting", "Page Splitting", "Mantiene il numero di pagina come confine logico.", "reference", "split_pages", "pdf pagination"),
    ),
)

_PREPROCESSING = _group(
    "Preprocessing",
    PHASES[1],
    (
        _t("unicode-normalization", "Unicode Normalization", "Applica normalizzazione Unicode (NFC/NFKC).", "reference", "normalize_unicode", "text normalization", "form=NFC"),
        _t("whitespace-normalization", "Whitespace Normalization", "Compatta spazi, tabulazioni e interruzioni di riga.", "reference", "normalize_whitespace", "text cleaning"),
        _t("lowercasing", "Lowercasing", "Converte il testo in minuscolo per indicizzazione.", "reference", "lowercase_text", "text normalization"),
        _t("stopword-removal", "Stopword Removal", "Rimuove parole vuote specifiche per lingua.", "reference", "remove_stopwords", "lexical text", "language=en"),
        _t("stemming-porter", "Porter Stemming", "Riduce le parole alla radice con algoritmo Porter.", "reference", "stem_porter", "lexical stemming"),
        _t("stemming-snowball", "Snowball Stemming", "Stemming multilingua con algoritmo Snowball.", "reference", "stem_snowball", "lexical stemming", "language=en"),
        _t("lemmatization", "Lemmatization", "Riduce le forme flesse al lemma lessicale.", "provider", tags="nlp morphology"),
        _t("dehyphenation", "Dehyphenation", "Ricompone parole spezzate a fine riga.", "reference", "dehyphenate", "text cleaning"),
        _t("language-detection", "Language Detection", "Rileva la lingua del documento o della query.", "reference", "detect_language", "nlp metadata"),
        _t("exact-deduplication", "Exact Deduplication", "Rimuove documenti o chunk identici per hash.", "reference", "dedupe_exact", "dedup hash"),
        _t("minhash-deduplication", "MinHash Deduplication", "Individua near-duplicate con firme MinHash.", "integration", tags="dedup lsh"),
        _t("simhash-deduplication", "SimHash Deduplication", "Rileva similarità di documento con SimHash.", "reference", "dedupe_simhash", "dedup hash"),
        _t("pii-redaction", "PII Redaction", "Anonimizza email, telefoni e dati sensibili.", "reference", "redact_pii", "privacy security"),
        _t("toxic-content-filter", "Toxic Content Filter", "Filtra contenuti offensivi o non conformi.", "provider", tags="safety moderation"),
        _t("text-cleaning", "Text Cleaning", "Rimuove rumore tipico di PDF e pagine web.", "reference", "clean_text", "text cleaning"),
        _t("number-normalization", "Number Normalization", "Uniforma formati di numeri, date e valute.", "reference", "normalize_numbers", "text normalization"),
        _t("acronym-expansion", "Acronym Expansion", "Espande acronimi noti e definiti nel contesto.", "design", tags="nlp enrichment"),
        _t("spell-correction", "Spell Correction", "Corregge errori ortografici prima della ricerca.", "reference", "correct_spelling", "nlp query"),
        _t("transliteration", "Transliteration", "Converte alfabeti diversi in forma comparabile.", "reference", "transliterate", "nlp multilingual"),
        _t("sentence-splitting", "Sentence Splitting", "Divide il testo in frasi mantenendo i confini.", "reference", "sentences", "nlp segmentation"),
        _t("tokenization", "Tokenization", "Suddivide il testo in token per la fase lessicale.", "reference", "tokenize", "nlp lexical"),
        _t("phrase-normalization", "Phrase Normalization", "Normalizza forme plurali e varianti di frase.", "design", tags="nlp lexical"),
        _t("quality-filtering", "Quality Filtering", "Scarta chunk troppo corti, vuoti o ripetitivi.", "reference", "filter_low_quality", "quality cleaning", "min_chars=40"),
        _t("near-duplicate-clustering", "Near-duplicate Clustering", "Raggruppa passaggi quasi identici tra documenti.", "design", tags="dedup clustering"),
        _t("date-normalization", "Date Normalization", "Converte date in formato ISO confrontabile.", "reference", "normalize_dates", "temporal text"),
        _t("url-normalization", "URL Normalization", "Rimuove parametri di tracciamento dagli URL.", "reference", "normalize_urls", "web links"),
        _t("html-entity-decoding", "HTML Entity Decoding", "Decodifica entità HTML come ``&amp;``.", "reference", "decode_entities", "html cleaning"),
        _t("emoji-handling", "Emoji Handling", "Rimuove o sostituisce emoji dal testo indicizzato.", "reference", "handle_emoji", "text cleaning"),
    ),
)

_CHUNKING = _group(
    "Chunking",
    PHASES[2],
    (
        _t("fixed-size-chunking", "Fixed-size Chunking", "Divide il testo in blocchi di lunghezza costante.", "reference", "chunk_documents", "chunking fixed", "size=512 overlap=64"),
        _t("fixed-overlap-chunking", "Fixed-overlap Chunking", "Aggiunge sovrapposizione tra blocchi consecutivi.", "reference", "chunk_documents", "chunking overlap", "overlap=64"),
        _t("recursive-chunking", "Recursive Chunking", "Taglia rispettando prima paragrafi e frasi.", "reference", "chunk_recursive", "chunking recursive structure"),
        _t("character-chunking", "Character Chunking", "Suddivide in base al numero di caratteri.", "reference", "chunk_documents", "chunking character"),
        _t("token-chunking", "Token Chunking", "Suddivide in base ai token del modello.", "reference", "chunk_tokens", "chunking token", "max_tokens=512"),
        _t("word-chunking", "Word Chunking", "Suddivide in base al numero di parole.", "reference", "chunk_words", "chunking word"),
        _t("sentence-chunking", "Sentence Chunking", "Usa le frasi come unità indivisibile.", "reference", "chunk_sentences", "chunking sentence"),
        _t("paragraph-chunking", "Paragraph Chunking", "Usa i paragrafi come unità di chunk.", "reference", "chunk_documents", "chunking paragraph"),
        _t("semantic-chunking", "Semantic Chunking", "Taglia dove cambia la similarità semantica.", "reference", "chunk_semantic", "chunking semantic", "threshold=0.75"),
        _t("llm-based-chunking", "LLM-based Chunking", "Chiede a un LLM di individuare confini coerenti.", "provider", tags="chunking llm"),
        _t("proposition-chunking", "Proposition Chunking", "Scompone il testo in proposizioni atomiche.", "provider", "chunk_propositions", "chunking proposition llm"),
        _t("hierarchical-chunking", "Hierarchical Chunking", "Costruisce livelli di chunk padri e figli.", "reference", "build_parent_child", "chunking hierarchical", "levels=2"),
        _t("raptor-chunking", "RAPTOR Chunking", "Costruisce un albero di riassunti ricorsivi.", "design", "chunk_raptor", "chunking raptor tree"),
        _t("late-chunking", "Late Chunking", "Genera embeddings token prima di tagliare il testo.", "provider", tags="chunking embedding late"),
        _t("contextual-retrieval-chunking", "Contextual Retrieval", "Aggiunge contesto generato a ogni chunk prima dell'indicizzazione.", "provider", tags="chunking contextual llm"),
        _t("parent-child-chunking", "Parent-Child Chunking", "Recupera figli piccoli e restituisce il padre più ampio.", "reference", "build_parent_child", "chunking parent-child"),
        _t("sentence-window-retrieval", "Sentence Window Retrieval", "Circonda la frase trovata con le frasi vicine.", "reference", "sentence_window_chunks", "chunking window retrieval", "window=2"),
        _t("cascading-chunking", "Cascading Chunking", "Applica strategie diverse in modo progressivo.", "design", tags="chunking cascading multi"),
        _t("multi-strategy-chunking", "Multi-strategy Chunking", "Combina regole strutturali, semantiche e di dimensione.", "reference", "chunk_multi_strategy", "chunking hybrid multi"),
        _t("sliding-window-chunking", "Sliding Window Chunking", "Finestra mobile con passo configurabile.", "reference", "chunk_documents", "chunking sliding", "stride=256"),
        _t("structure-aware-chunking", "Structure-aware Chunking", "Rispetta la struttura logica del documento.", "reference", "chunk_recursive", "chunking structure"),
        _t("markdown-header-chunking", "Markdown Header Chunking", "Usa i titoli Markdown come confini principali.", "reference", "chunk_by_headers", "chunking markdown headers"),
        _t("table-aware-chunking", "Table-aware Chunking", "Mantiene righe e intestazioni di tabella insieme.", "design", tags="chunking table structure"),
        _t("code-aware-chunking", "Code-aware Chunking", "Taglia sorgenti su confini di funzioni e classi.", "design", tags="chunking code ast"),
        _t("qa-based-chunking", "QA-based Chunking", "Genera coppie domanda-risposta come unità di recupero.", "provider", tags="chunking synthetic qa"),
        _t("topic-based-chunking", "Topic-based Chunking", "Raggruppa paragrafi appartenenti allo stesso argomento.", "design", tags="chunking topic"),
        _t("dynamic-chunking", "Dynamic Chunking", "Adatta la dimensione del blocco alla densità informativa.", "design", tags="chunking adaptive"),
        _t("similarity-threshold-chunking", "Similarity Threshold Chunking", "Unisce frasi finché la similarità supera la soglia.", "reference", "chunk_semantic", "chunking semantic threshold", "threshold=0.8"),
        _t("context-enriched-chunking", "Context-enriched Chunking", "Aggiunge titolo e percorso prima di ogni chunk.", "provider", tags="chunking contextual metadata"),
        _t("agentic-chunking", "Agentic Chunking", "Un agente decide come suddividere il documento.", "design", tags="chunking agent llm"),
        _t("passage-chunking", "Passage Chunking", "Usa passaggi di dimensione media ottimizzata per embeddings.", "reference", "chunk_documents", "chunking passage", "size=400"),
        _t("chunk-size-optimization", "Chunk Size Optimization", "Sceglie la dimensione sperimentalmente sul dataset.", "design", tags="chunking tuning evaluation"),
        _t("overlap-optimization", "Overlap Optimization", "Regola la sovrapposizione per bilanciare recall e costo.", "design", tags="chunking tuning overlap"),
    ),
)

_ENRICHMENT = _group(
    "Enrichment",
    PHASES[3],
    (
        _t("named-entity-recognition", "Named Entity Recognition", "Estrae persone, organizzazioni e luoghi dai chunk.", "provider", "extract_entities", "ner entities nlp"),
        _t("relation-extraction", "Relation Extraction", "Individua relazioni tra entità nel testo.", "provider", tags="nlp graph relations"),
        _t("keyphrase-extraction", "Keyphrase Extraction", "Estrae le parole chiave più rappresentative.", "reference", "extract_keyphrases", "keyphrase nlp"),
        _t("rake-keyphrase", "RAKE Keyphrase Extraction", "Estrae frasi chiave con l'algoritmo RAKE.", "reference", "extract_keyphrases_rake", "keyphrase rake"),
        _t("yake-keyphrase", "YAKE Keyphrase Extraction", "Estrae parole chiave senza supervisione con YAKE.", "reference", "extract_keyphrases_yake", "keyphrase yake"),
        _t("keybert-keyphrase", "KeyBERT", "Seleziona keyphrase semantiche con embeddings.", "provider", tags="keyphrase embedding"),
        _t("entity-linking", "Entity Linking", "Collega le entità a un knowledge base esterno.", "provider", tags="ner knowledge-graph"),
        _t("document-summarization", "Document Summarization", "Genera riassunti da usare come metadata di ricerca.", "provider", "summarize_document", "summary llm"),
        _t("synthetic-qa-generation", "Synthetic QA Generation", "Crea domande e risposte artificiali dai chunk.", "provider", "generate_synthetic_qa", "synthetic qa llm"),
        _t("hypothetical-question-generation", "Hypothetical Question Generation", "Genera domande plausibili per ogni passaggio.", "provider", tags="synthetic question llm"),
        _t("metadata-tagging", "Metadata Tagging", "Assegna tag strutturati a documenti e chunk.", "design", tags="metadata taxonomy"),
        _t("document-classification", "Document Classification", "Classifica i documenti per categoria o dominio.", "provider", tags="classification metadata"),
        _t("sentiment-analysis", "Sentiment Analysis", "Estrae il sentiment come metadata di filtro.", "provider", tags="classification sentiment"),
        _t("topic-modeling-lda", "Topic Modeling (LDA)", "Assegna topic latenti con LDA.", "integration", tags="topic modeling unsupervised"),
        _t("bertopic-topic-modeling", "BERTopic", "Cluster embeddings in topic interpretabili.", "provider", tags="topic modeling embedding"),
        _t("contextual-prefix", "Contextual Prefix", "Antepose titolo e contesto del documento al chunk.", "reference", "add_contextual_prefix", "enrichment prefix metadata", "include_title=true"),
        _t("title-prefix-enrichment", "Title Prefix Enrichment", "Aggiunge il titolo del documento a ogni blocco.", "reference", "add_contextual_prefix", "enrichment title"),
        _t("timestamp-metadata", "Timestamp Metadata", "Registra date di creazione e aggiornamento.", "reference", "attach_timestamps", "enrichment temporal metadata"),
        _t("provenance-metadata", "Provenance Metadata", "Conserva sorgente, pagina e offset del chunk.", "reference", "attach_provenance", "enrichment provenance citation"),
        _t("keyword-tagging", "Keyword Tagging", "Estrae parole chiave semplici come filtri di ricerca.", "reference", "extract_keyphrases", "enrichment keywords"),
        _t("glossary-linking", "Glossary Linking", "Collega termini al glossario aziendale.", "design", tags="enrichment taxonomy"),
        _t("taxonomy-mapping", "Taxonomy Mapping", "Mappa i contenuti su una tassonomia controllata.", "design", tags="enrichment taxonomy classification"),
        _t("chunk-quality-scoring", "Chunk Quality Scoring", "Valuta completezza e coerenza di ogni chunk.", "reference", "score_chunk_quality", "enrichment quality"),
        _t("cross-reference-linking", "Cross-reference Linking", "Collega chunk che citano la stessa entità.", "design", tags="enrichment graph links"),
        _t("entity-embedding-link", "Entity Embedding Link", "Associa embedding a entità riconosciute.", "design", tags="enrichment entity embedding"),
        _t("metadata-schema-extraction", "Metadata Schema Extraction", "Deriva chiavi metadata dai documenti sorgente.", "design", tags="enrichment schema metadata"),
        _t("multilingual-translation", "Multilingual Translation", "Traduce chunk per indicizzazione cross-lingua.", "provider", tags="translation multilingual"),
        _t("semantic-labeling", "Semantic Labeling", "Assegna etichette semantiche con un modello.", "provider", tags="enrichment labeling"),
    ),
)

_EMBEDDINGS = _group(
    "Embeddings",
    PHASES[4],
    (
        _t("tfidf-embeddings", "TF-IDF", "Rappresentazione sparse basata su frequenza e IDF.", "reference", "tfidf_vectorize", "sparse lexical tfidf"),
        _t("bm25-sparse-weights", "BM25 Sparse Weights", "Pesi lessicali BM25 come vettore sparso.", "reference", "bm25_scores", "sparse lexical bm25", "k1=1.5 b=0.75"),
        _t("e5-embeddings", "E5 Embeddings", "Embedding dense E5 di Microsoft per retrieval.", "provider", tags="dense model microsoft"),
        _t("e5-instruct", "E5 Instruct", "Variante E5 con istruzioni per query e documento.", "provider", tags="dense instruction retrieval"),
        _t("bge-embeddings", "BGE Embeddings", "Famiglia di embedding BGE ottimizzata per ricerca.", "provider", tags="dense model bge"),
        _t("bge-m3-embeddings", "BGE-M3", "Embedding multilingua ibridi dense e sparse.", "provider", tags="dense sparse multilingual"),
        _t("gte-embeddings", "GTE Embeddings", "Embedding GTE con supporto per testi lunghi.", "provider", tags="dense model gte"),
        _t("jina-embeddings", "Jina Embeddings", "Embedding dense forniti da Jina AI.", "provider", tags="dense model jina"),
        _t("nomic-embeddings", "Nomic Embed", "Embedding open source Nomic con Matryoshka.", "provider", tags="dense model nomic"),
        _t("qwen-embeddings", "Qwen Embeddings", "Embedding multilingua della famiglia Qwen.", "provider", tags="dense model qwen"),
        _t("voyage-embeddings", "Voyage Embeddings", "Embedding Voyage AI per ricerca e domini specialistici.", "provider", tags="dense model voyage"),
        _t("cohere-embeddings", "Cohere Embed", "Embedding Cohere con modalità search distinction.", "provider", tags="dense model cohere"),
        _t("openai-embeddings", "OpenAI Embeddings", "Embedding dense via API OpenAI.", "provider", tags="dense model openai"),
        _t("minilm-embeddings", "MiniLM Embeddings", "Embedding leggeri MiniLM per bassa latenza.", "provider", tags="dense model lightweight"),
        _t("mpnet-embeddings", "MPNet Embeddings", "Embedding MPNet con contesto bidirezionale.", "provider", tags="dense model mpnet"),
        _t("sentence-bert", "Sentence-BERT", "Embedding di frasi ottenuti con Siamese BERT.", "provider", tags="dense model sbert"),
        _t("contriever-embeddings", "Contriever", "Embedding dense non supervisionati per passages.", "provider", tags="dense model contriever"),
        _t("dpr-embeddings", "DPR Embeddings", "Dense Passage Retriever con encoder separati.", "provider", tags="dense model dpr"),
        _t("colbert", "ColBERT", "Rappresentazione multi-vettore con MaxSim.", "provider", tags="multivector late-interaction colbert"),
        _t("colbertv2", "ColBERTv2", "ColBERT con compressione residua e qualità superiore.", "provider", tags="multivector late-interaction colbert"),
        _t("late-interaction", "Late Interaction", "Interazione token-level tra query e documento.", "design", "max_similarity", "multivector maxsim"),
        _t("splade", "SPLADE", "Espansione lessicale sparsa appresa con transformer.", "provider", tags="sparse learned expansion"),
        _t("unicoil", "uniCOIL", "Rappresentazione sparsa con peso per token della query.", "provider", tags="sparse learned unicoil"),
        _t("deepimpact", "DeepImpact", "Impatto appreso dei termini per ranking sparsa.", "provider", tags="sparse learned deepimpact"),
        _t("clip-embeddings", "CLIP Embeddings", "Embedding congiunti testo-immagine CLIP.", "provider", tags="multimodal clip vision"),
        _t("siglip-embeddings", "SigLIP Embeddings", "Embedding multimediali SigLIP con sigmoid loss.", "provider", tags="multimodal siglip vision"),
        _t("matryoshka-embeddings", "Matryoshka Embeddings", "Vettori troncabili a dimensioni progressive.", "provider", "truncate_embedding", "matryoshka dimensionality", "dim=256"),
        _t("int8-quantization", "INT8 Quantization", "Quantizzazione a 8 bit degli embedding.", "reference", "quantize_int8", "quantization compression"),
        _t("binary-quantization", "Binary Quantization", "Riduce i vettori a bit con confronto Hamming.", "reference", "quantize_binary", "quantization binary"),
        _t("product-quantization", "Product Quantization", "Comprime i vettori in sottospazi quantizzati.", "integration", tags="quantization pq index"),
        _t("embedding-normalization", "Embedding Normalization", "Normalizza i vettori per similarità coseno.", "reference", "normalize_vector", "dense normalization", "norm=l2"),
        _t("pca-dimensionality-reduction", "PCA Dimensionality Reduction", "Riduce la dimensionalità con PCA.", "integration", tags="dense compression pca"),
        _t("asymmetric-embeddings", "Asymmetric Embeddings", "Encoder diversi per query e documento.", "design", tags="dense retrieval asymmetric"),
        _t("symmetric-embeddings", "Symmetric Embeddings", "Lo stesso encoder per query e documento.", "design", tags="dense retrieval symmetric"),
        _t("instruction-tuned-embeddings", "Instruction-tuned Embeddings", "Prefissi di istruzione specifici per attività.", "provider", tags="dense instruction prompt"),
        _t("domain-finetuned-embeddings", "Domain-adapted Embeddings", "Fine-tuning del modello sul dominio aziendale.", "provider", tags="dense finetuning domain"),
        _t("code-embeddings", "Code Embeddings", "Embedding specializzati per codice sorgente.", "provider", tags="dense code retrieval"),
        _t("multilingual-embeddings", "Multilingual Embeddings", "Embedding allineati tra più lingue.", "provider", tags="dense multilingual"),
        _t("mean-pooling", "Mean Pooling", "Media dei vettori token per ottenere il vettore del testo.", "reference", "pool_mean", "embedding pooling"),
        _t("cls-pooling", "CLS Pooling", "Usa il vettore speciale CLS come rappresentazione.", "reference", "pool_cls", "embedding pooling"),
        _t("embedding-model-versioning", "Embedding Model Versioning", "Registra modello e versione usati per ogni indice.", "reference", "track_embedding_model", "embedding metadata reproducibility"),
    ),
)

_INDEXING = _group(
    "Indexing & Storage",
    PHASES[4],
    (
        _t("flat-index", "Flat Index", "Confronto esaustivo: massima precisione, costo lineare.", "reference", "build_flat_index", "index brute-force exact"),
        _t("ivf-index", "IVF Index", "Inverted file index con clustering dei vettori.", "integration", tags="index ivf approximate", parameters="nlist=100"),
        _t("ivf-pq-index", "IVF-PQ Index", "IVF combinato con product quantization.", "integration", tags="index ivf pq compression"),
        _t("pq-index", "PQ Index", "Indice basato esclusivamente su product quantization.", "integration", tags="index pq compression"),
        _t("opq-index", "OPQ Index", "Ottimizza la rotazione prima della quantizzazione.", "integration", tags="index opq quantization"),
        _t("hnsw-index", "HNSW Index", "Grafo gerarchico navigabile per ricerca ANN.", "integration", tags="index hnsw graph ann", parameters="M=16 ef=128"),
        _t("hnsw-pq-index", "HNSW-PQ Index", "HNSW con vettori compressi tramite PQ.", "integration", tags="index hnsw pq hybrid"),
        _t("diskann-index", "DiskANN Index", "Grafo ANN ottimizzato per dati su disco.", "integration", tags="index disk ann graph"),
        _t("annoy-index", "Annoy Index", "Foresta di alberi casuali per ricerca approssimata.", "integration", tags="index annoy trees ann"),
        _t("scann-index", "ScaNN Index", "Ricerca ANN di Google con quantizzazione anisotropica.", "integration", tags="index scann ann"),
        _t("lsh-index", "LSH Index", "Locality-sensitive hashing per candidati rapidi.", "reference", "build_lsh_index", "index lsh ann", "bands=16"),
        _t("inverted-index", "Inverted Index", "Posting list termine -> documento per ricerca sparse.", "reference", "build_inverted_index", "index sparse lexical"),
        _t("inverted-graph-hybrid", "Inverted-Graph Hybrid", "Combina posting list lessicali e grafo vettoriale.", "design", tags="index hybrid graph sparse"),
        _t("full-text-index", "Full-text Index", "Indice testuale con tokenizzazione e pesi BM25.", "reference", "build_inverted_index", "index fulltext search"),
        _t("metadata-index", "Metadata Index", "Indice secondario su campi strutturati per filtri.", "reference", "build_metadata_index", "index metadata filter"),
        _t("scalar-quantization-index", "Scalar Quantization Index", "Riduce la precisione dei vettori a 8/16 bit.", "reference", "quantize_int8", "index quantization"),
        _t("binary-index", "Binary Index", "Indice di vettori binarizzati con distanza Hamming.", "reference", "quantize_binary", "index binary compression"),
        _t("sharded-index", "Sharded Index", "Suddivide l'indice in shard orizzontali.", "integration", tags="index scalability sharding"),
        _t("replicated-index", "Replicated Index", "Repliche dell'indice per disponibilità e throughput.", "integration", tags="index scalability replication"),
        _t("document-store", "Document Store", "Archivio dei documenti originali e dei chunk.", "integration", tags="storage documents persistence"),
        _t("vector-store", "Vector Store", "Archivio specializzato per embedding e metadati.", "integration", tags="storage vectors database"),
        _t("hybrid-store", "Hybrid Store", "Archivia rappresentazioni sparse e dense nello stesso indice.", "integration", tags="storage hybrid sparse dense"),
        _t("graph-index", "Graph Index", "Memorizza entità e relazioni come grafo.", "integration", tags="storage graph knowledge"),
        _t("hierarchical-index", "Hierarchical Index", "Indice a livelli per navigazione coarse-to-fine.", "design", tags="index hierarchical structure"),
        _t("spillover-index", "Spillover Index", "Ripete vettori vicini ai confini dei cluster.", "design", tags="index ivf recall"),
        _t("incremental-index-update", "Incremental Index Update", "Aggiorna solo i vettori modificati senza rebuild.", "design", tags="index maintenance delta"),
        _t("index-compaction", "Index Compaction", "Compatta segmenti e rimuove vettori obsoleti.", "integration", tags="index maintenance storage"),
        _t("index-parameter-tuning", "Index Parameter Tuning", "Ottimizza parametri ANN su recall e latenza.", "design", tags="index tuning evaluation"),
    ),
)

_QUERY = _group(
    "Query Processing",
    PHASES[5],
    (
        _t("query-rewrite", "Query Rewrite", "Riformula la query per migliorare il recupero.", "reference", "rewrite_query", "query rewrite nlp"),
        _t("query-expansion", "Query Expansion", "Aggiunge termini correlati alla query originale.", "reference", "expand_query", "query expansion lexical"),
        _t("synonym-expansion", "Synonym Expansion", "Espande la query con sinonimi da thesaurus.", "reference", "expand_query_synonyms", "query expansion synonyms", "source=wordnet"),
        _t("query-decomposition", "Query Decomposition", "Suddivide una query complessa in sotto-query.", "provider", "decompose_query", "query decomposition multi-hop"),
        _t("hyde", "HyDE", "Genera un documento ipotetico e lo usa come query.", "provider", "hypothetical_document", "query hyde llm"),
        _t("step-back-prompting", "Step-back Prompting", "Genera una domanda più astratta per ampliare il contesto.", "provider", tags="query stepback llm"),
        _t("query2doc", "Query2doc", "Genera un passaggio pseudo-rilevante dalla query.", "provider", tags="query expansion llm"),
        _t("rq-rag", "RQ-RAG", "Raffina la query con riscrittura, decomposizione e ampliamento.", "provider", tags="query refinement llm"),
        _t("multi-hop-query-planning", "Multi-hop Query Planning", "Pianifica una sequenza di recuperi dipendenti.", "design", tags="query multihop planning"),
        _t("query-routing", "Query Routing", "Indirizza la query al retriever o all'indice più adatto.", "reference", "route_query", "query routing adaptive"),
        _t("query-planning", "Query Planning", "Costruisce un piano di esecuzione prima del recupero.", "design", "plan_query", "query planning agent"),
        _t("query-intent-classification", "Query Intent Classification", "Classifica l'intento per scegliere la strategia.", "provider", tags="query classification llm"),
        _t("query-type-detection", "Query Type Detection", "Distingue domande fattuali, analitiche e procedimentali.", "reference", "detect_query_type", "query classification rules"),
        _t("query-entity-extraction", "Query Entity Extraction", "Estrae entità dalla query per filtri e grafi.", "provider", tags="query ner entities"),
        _t("query-spell-correction", "Query Spell Correction", "Corregge errori di battitura nella query.", "reference", "correct_query", "query spelling"),
        _t("query-normalization", "Query Normalization", "Applica alla query la stessa normalizzazione del corpus.", "reference", "normalize_query", "query normalization"),
        _t("query-clarification", "Query Clarification", "Chiede all'utente di chiarire le domande vaghe.", "design", tags="query clarification dialogue"),
        _t("query-compression", "Query Compression", "Riduce query lunghe ai soli termini informativi.", "provider", tags="query compression llm"),
        _t("self-query-metadata-filter", "Self-query Metadata Filter", "Deriva filtri strutturati dal testo della query.", "provider", tags="query metadata filter llm"),
        _t("multi-query-generation", "Multi-query Generation", "Genera più varianti della stessa query.", "provider", "generate_queries", "query multi llm", "n=4"),
        _t("contextual-query-compaction", "Contextual Query Compaction", "Compatta la query usando la cronologia della conversazione.", "provider", tags="query conversational memory"),
        _t("subquery-generation", "Sub-query Generation", "Produce sotto-domande da eseguire in parallelo.", "provider", tags="query decomposition parallel"),
        _t("query-embedding", "Query Embedding", "Codifica la query nello spazio degli embedding.", "reference", "embed_text", "query dense embedding"),
        _t("query-cache-key", "Query Cache Key", "Calcola una chiave stabile per il caching della query.", "reference", "cache_key", "query cache deterministic"),
        _t("query-rephrasing", "Query Rephrasing", "Riscrive la query mantenendone il significato.", "provider", tags="query rewrite llm"),
        _t("backtranslation-expansion", "Backtranslation Expansion", "Traduce avanti e indietro per generare varianti.", "provider", tags="query expansion translation"),
        _t("pseudo-relevance-feedback", "Pseudo Relevance Feedback", "Usa i documenti migliori per espandere la query.", "design", tags="query expansion prf"),
        _t("query-term-weighting", "Query Term Weighting", "Assegna pesi diversi ai termini della query.", "reference", "weight_query_terms", "query lexical weights"),
        _t("query-length-adaptation", "Query Length Adaptation", "Adatta la strategia alla lunghezza della query.", "design", tags="query adaptive"),
        _t("query-language-detection", "Query Language Detection", "Rileva la lingua per scegliere analizzatore e modello.", "reference", "detect_language", "query multilingual"),
    ),
)

_RETRIEVAL = _group(
    "Retrieval",
    PHASES[6],
    (
        _t("sparse-retrieval", "Sparse Retrieval", "Recupera con corrispondenze lessicali esatte.", "reference", "bm25_scores", "retrieval sparse lexical"),
        _t("dense-retrieval", "Dense Retrieval", "Recupera per similarità tra embedding.", "reference", "dense_scores", "retrieval dense vector"),
        _t("hybrid-retrieval", "Hybrid Retrieval", "Combina recupero denso e sparsa in un'unica corsa.", "reference", "retrieve", "retrieval hybrid dense sparse", "alpha=0.5 top_k=20"),
        _t("bm25", "BM25 Retrieval", "Ranking lessicale BM25 classico.", "reference", "bm25_scores", "retrieval bm25 lexical", "k1=1.5 b=0.75"),
        _t("bm25-plus", "BM25+", "BM25 con limite inferiore sul contributo di frequenza.", "reference", "bm25_plus_scores", "retrieval bm25 variant", "delta=1.0"),
        _t("bm25l", "BM25L", "BM25 con normalizzazione della lunghezza modificata.", "reference", "bm25l_scores", "retrieval bm25 variant"),
        _t("tfidf-retrieval", "TF-IDF Retrieval", "Ranking per similarità coseno TF-IDF.", "reference", "tfidf_retrieve", "retrieval tfidf lexical"),
        _t("vector-similarity-search", "Vector Similarity Search", "Ricerca ANN per coseno o distanza euclidea.", "reference", "search_vectors", "retrieval vector ann", "metric=cosine top_k=20"),
        _t("maxsim-retrieval", "MaxSim Retrieval", "Recupero multi-vettore con similarità massima per token.", "provider", "max_similarity", "retrieval multivector colbert"),
        _t("graph-retrieval", "Graph Retrieval", "Naviga un grafo di documenti ed entità.", "integration", tags="retrieval graph knowledge"),
        _t("knowledge-graph-retrieval", "Knowledge Graph Retrieval", "Interroga un knowledge graph strutturato.", "integration", tags="retrieval knowledge-graph triples"),
        _t("lightrag", "LightRAG", "Recupero su grafo con indicizzazione incrementale economica.", "provider", tags="retrieval graph llm"),
        _t("hipporag", "HippoRAG", "Recupero ispirato alla memoria episodica con PageRank.", "integration", tags="retrieval graph pagerank"),
        _t("g-retriever", "G-Retriever", "Recupero su grafo con GNN e generazione testuale.", "provider", tags="retrieval graph gnn llm"),
        _t("personalized-pagerank", "Personalized PageRank", "Propaga rilevanza da semi selezionati nel grafo.", "reference", "personalized_pagerank", "retrieval graph ranking", "damping=0.85"),
        _t("gnn-retrieval", "GNN Retrieval", "Usa graph neural network per punteggi di rilevanza.", "provider", tags="retrieval graph gnn"),
        _t("subgraph-retrieval", "Subgraph Retrieval", "Estrae il sotto-grafo rilevante intorno alle entità.", "design", tags="retrieval graph traversal"),
        _t("hierarchical-retrieval", "Hierarchical Retrieval", "Prima seleziona il documento, poi il chunk rilevante.", "design", tags="retrieval hierarchical two-stage"),
        _t("metadata-filtered-retrieval", "Metadata-filtered Retrieval", "Applica filtri strutturati prima del ranking.", "reference", "filter_documents", "retrieval metadata filter"),
        _t("multi-query-retrieval", "Multi-query Retrieval", "Esegue più varianti della query e unisce i risultati.", "design", tags="retrieval multi fusion"),
        _t("iterative-retrieval", "Iterative Retrieval", "Recupera ripetutamente usando i risultati precedenti.", "design", tags="retrieval iterative loop"),
        _t("temporal-retrieval", "Temporal Retrieval", "Usa intervalli di tempo e freschezza nel ranking.", "design", tags="retrieval temporal metadata"),
        _t("cross-lingual-retrieval", "Cross-lingual Retrieval", "Recupera documenti in lingue diverse dalla query.", "provider", tags="retrieval multilingual embedding"),
        _t("code-retrieval", "Code Retrieval", "Recupera funzioni e file sorgente rilevanti.", "design", tags="retrieval code ast"),
        _t("table-retrieval", "Table Retrieval", "Recupera tabelle e righe pertinenti.", "design", tags="retrieval table structured"),
        _t("sql-retrieval", "SQL Retrieval", "Genera ed esegue query SQL sul database.", "integration", tags="retrieval sql database"),
        _t("citation-retrieval", "Citation Retrieval", "Segue catene di citazioni tra documenti accademici.", "design", tags="retrieval citation graph"),
        _t("graph-walk-retrieval", "Graph Walk Retrieval", "Esplora il grafo con cammini guidati dalla rilevanza.", "design", tags="retrieval graph traversal"),
        _t("full-text-search", "Full-text Search", "Ricerca testuale con operatori booleani e frasi.", "reference", "search_fulltext", "retrieval fulltext lexical"),
        _t("fuzzy-search", "Fuzzy Search", "Tolera errori di battitura nella corrispondenza dei termini.", "reference", "search_fuzzy", "retrieval fuzzy lexical"),
        _t("web-search-retrieval", "Web Search Retrieval", "Recupera prove da un motore di ricerca esterno.", "integration", tags="retrieval web external"),
        _t("recursive-retrieval", "Recursive Retrieval", "Da un padre recupera i figli più rilevanti e viceversa.", "design", tags="retrieval recursive hierarchical"),
        _t("long-context-retrieval", "Long-context Retrieval", "Affida al modello un contesto esteso invece del top-K.", "provider", tags="retrieval long-context llm"),
        _t("semantic-search", "Semantic Search", "Ricerca per significato e non per parole esatte.", "reference", "dense_scores", "retrieval semantic dense"),
        _t("lexical-search", "Lexical Search", "Ricerca basata sulla corrispondenza esatta dei termini.", "reference", "lexical_score", "retrieval lexical exact"),
        _t("context-aware-retrieval", "Context-aware Retrieval", "Usa la cronologia della conversazione nella ricerca.", "design", tags="retrieval conversational memory"),
        _t("retrieval-extended", "Extended Retrieval", "Pipeline di recupero con varianti configurabili.", "reference", "retrieve_extended", "retrieval pipeline extended"),
    ),
)

_FUSION = _group(
    "Fusion",
    PHASES[6],
    (
        _t("reciprocal-rank-fusion", "Reciprocal Rank Fusion (RRF)", "Unisce classifiche sommando l'inverso del rango.", "reference", "reciprocal_rank_fusion", "fusion rrf robust", "k=60"),
        _t("weighted-rrf", "Weighted RRF", "RRF con pesi diversi per ogni retriever.", "reference", "fusion_rankings", "fusion rrf weighted", "weights=1.0"),
        _t("linear-combination", "Linear Combination", "Somma pesata dei punteggi normalizzati.", "reference", "fuse_scores", "fusion linear weighted"),
        _t("relative-score-fusion", "Relative Score Fusion", "Fonde punteggi relativi al massimo di ogni lista.", "reference", "fuse_scores", "fusion relative normalization"),
        _t("distribution-based-fusion", "Distribution-based Fusion", "Normalizza punteggi secondo la distribuzione osservata.", "reference", "fuse_distributions", "fusion distribution"),
        _t("combsum", "CombSUM", "Somma i punteggi di ciascun retriever.", "reference", "fuse_scores", "fusion combsum scores"),
        _t("combmnz", "CombMNZ", "CombSUM moltiplicato per il numero di liste di supporto.", "reference", "fuse_combmnz", "fusion combmnz scores"),
        _t("borda-count", "Borda Count", "Assegna punti in base alla posizione in ogni classifica.", "reference", "fusion_rankings", "fusion borda rank"),
        _t("learned-fusion", "Learned Fusion", "Apprende i pesi di fusione da dati di addestramento.", "design", tags="fusion learning-to-rank"),
        _t("llm-fusion", "LLM Fusion", "L'LLM decide quali fonti privilegiare nella fusione.", "provider", tags="fusion llm ranking"),
        _t("rank-aggregation", "Rank Aggregation", "Aggrega più classifiche in un ordinamento consensus.", "reference", "fusion_rankings", "fusion rank aggregation"),
        _t("min-max-fusion", "Min-Max Fusion", "Porta i punteggi in [0,1] prima della somma.", "reference", "min_max_normalize", "fusion normalization minmax"),
        _t("zscore-fusion", "Z-score Fusion", "Standardizza i punteggi prima di combinarli.", "reference", "fuse_zscore", "fusion normalization zscore"),
        _t("bayesian-fusion", "Bayesian Fusion", "Combina evidenze con un modello probabilistico.", "design", tags="fusion probabilistic ranking"),
        _t("ensemble-fusion", "Ensemble Fusion", "Combina più modelli di ranking eterogenei.", "design", tags="fusion ensemble models"),
        _t("max-score-fusion", "Max Score Fusion", "Usa il punteggio massimo ottenuto tra i retriever.", "reference", "fuse_scores", "fusion max"),
        _t("score-normalization", "Score Normalization", "Rende confrontabili punteggi di scale diverse.", "reference", "min_max_normalize", "fusion normalization"),
        _t("round-robin-fusion", "Round-robin Fusion", "Alterna i candidati dalle varie liste.", "reference", "fusion_rankings", "fusion interleaving"),
    ),
)

_RERANKING = _group(
    "Reranking",
    PHASES[7],
    (
        _t("cross-encoder-reranking", "Cross-encoder Reranking", "Valuta coppie query-documento in modo congiunto.", "provider", "rerank_candidates", "reranking cross-encoder"),
        _t("minilm-cross-encoder", "MiniLM Cross-encoder", "Reranker cross-encoder compatto e veloce.", "provider", tags="reranking cross-encoder minilm"),
        _t("bge-reranker", "BGE Reranker", "Reranker cross-encoder della famiglia BGE.", "provider", tags="reranking cross-encoder bge"),
        _t("jina-reranker", "Jina Reranker", "Reranker fornito da Jina AI.", "provider", tags="reranking cross-encoder jina"),
        _t("cohere-rerank", "Cohere Rerank", "Reranking via API Cohere.", "provider", tags="reranking cohere external"),
        _t("maxsim-reranking", "MaxSim Reranking", "Reranking multi-vettore con MaxSim token-level.", "reference", "max_similarity", "reranking multivector maxsim"),
        _t("rankgpt", "RankGPT", "Reranking listwise eseguito da un LLM.", "provider", tags="reranking llm listwise"),
        _t("rankllm", "RankLLM", "Reranking con LLM istruito per l'ordinamento.", "provider", tags="reranking llm listwise"),
        _t("lambdamart", "LambdaMART", "Learning-to-rank con gradient boosted trees.", "integration", tags="reranking ltr lambdamart"),
        _t("lambdarank", "LambdaRank", "Learning-to-rank ottimizzato per NDCG.", "integration", tags="reranking ltr lambdarank"),
        _t("ranknet", "RankNet", "Rete neurale pairwise per il ranking.", "integration", tags="reranking ltr neural"),
        _t("mmr-reranking", "MMR Reranking", "Bilancia rilevanza e novità con Maximal Marginal Relevance.", "reference", "mmr_select", "reranking mmr diversity", "lambda=0.5"),
        _t("dpp-reranking", "DPP Reranking", "Diversità tramite determinantal point process.", "reference", "dpp_rerank", "reranking dpp diversity"),
        _t("context-aware-reranking", "Context-aware Reranking", "Reranking che considera il contesto della conversazione.", "design", tags="reranking contextual dialogue"),
        _t("pointwise-reranking", "Pointwise Reranking", "Assegna un punteggio assoluto a ogni candidato.", "design", tags="reranking ltr pointwise"),
        _t("pairwise-reranking", "Pairwise Reranking", "Confronta coppie di candidati per ordinari.", "design", tags="reranking ltr pairwise"),
        _t("listwise-reranking", "Listwise Reranking", "Ottimizza l'intera lista di risultati.", "design", tags="reranking ltr listwise"),
        _t("monot5", "monoT5", "Reranker T5 con etichette rilevante/non rilevante.", "provider", tags="reranking transformer t5"),
        _t("monobert", "monoBERT", "Reranker BERT con testa di classificazione binaria.", "provider", tags="reranking transformer bert"),
        _t("colbert-reranking", "ColBERT Reranking", "Riordina con interazione tardiva multi-vettore.", "provider", tags="reranking colbert maxsim"),
        _t("llm-pairwise-reranking", "LLM Pairwise Reranking", "Confronta coppie di documenti tramite LLM.", "provider", tags="reranking llm pairwise"),
        _t("llm-listwise-reranking", "LLM Listwise Reranking", "Chiede all'LLM di ordinare l'intera lista.", "provider", tags="reranking llm listwise"),
        _t("score-threshold-reranking", "Score Threshold Reranking", "Filtra i candidati sotto una soglia di punteggio.", "reference", "rerank_candidates", "reranking threshold", "min_score=0.5"),
        _t("feature-based-reranking", "Feature-based Reranking", "Combina caratteristiche testuali, temporali e di fonte.", "design", tags="reranking features"),
        _t("diversity-reranking", "Diversity Reranking", "Penalizza risultati ridondanti tra loro.", "reference", "mmr_select", "reranking diversity"),
        _t("relevance-reranking", "Relevance Reranking", "Riordina usando il solo punteggio di rilevanza.", "reference", "rerank_candidates", "reranking relevance"),
        _t("rerank-pipeline", "Rerank Pipeline", "Applica più stadi di reranking in sequenza.", "design", tags="reranking cascade pipeline"),
    ),
)

_SELECTION = _group(
    "Selection & Filtering",
    PHASES[7],
    (
        _t("top-k-selection", "Top-K Selection", "Seleziona i primi K candidati per punteggio.", "reference", "select_candidates", "selection topk", "k=5"),
        _t("top-p-selection", "Top-P Selection", "Seleziona candidati fino a una probabilità cumulata.", "reference", "select_candidates", "selection topp", "p=0.9"),
        _t("threshold-selection", "Threshold Selection", "Mantiene solo i candidati sopra una soglia.", "reference", "select_candidates", "selection threshold", "min_score=0.6"),
        _t("adaptive-k", "Adaptive-K", "Sceglie K dinamicamente in base alla qualità dei risultati.", "reference", "select_candidates", "selection adaptive k"),
        _t("token-budget-selection", "Token-budget Selection", "Riempie il budget di token della finestra di contesto.", "reference", "select_candidates", "selection token budget", "max_tokens=4000"),
        _t("mmr-selection", "MMR Selection", "Massimizza rilevanza e diversità nella selezione.", "reference", "mmr_select", "selection mmr diversity", "lambda=0.7"),
        _t("deduplication", "Deduplication", "Elimina chunk duplicati o quasi identici.", "reference", "dedupe_candidates", "selection dedup"),
        _t("coverage-based-selection", "Coverage-based Selection", "Copre il maggior numero di fonti o argomenti.", "reference", "select_candidates", "selection coverage sources"),
        _t("reward-based-selection", "Reward-based Selection", "Seleziona secondo un modello di reward appreso.", "design", tags="selection reinforcement-learning"),
        _t("diversity-selection", "Diversity Selection", "Favorisce risultati semanticamente distinti.", "reference", "mmr_select", "selection diversity"),
        _t("source-diversity-filter", "Source Diversity Filter", "Limita il numero di chunk per singola fonte.", "reference", "filter_candidates", "selection source diversity", "max_per_source=2"),
        _t("freshness-filter", "Freshness Filter", "Predilige documenti aggiornati di recente.", "reference", "filter_candidates", "selection temporal freshness"),
        _t("acl-filter", "ACL Filter", "Filtra i chunk in base ai permessi dell'utente.", "design", tags="selection security access-control"),
        _t("metadata-filter", "Metadata Filter", "Filtra per lingua, autore, tipo o altri campi.", "reference", "filter_documents", "selection metadata structured"),
        _t("score-margin-selection", "Score Margin Selection", "Richiede uno scarto minimo tra candidati vicini.", "reference", "select_candidates", "selection margin", "margin=0.05"),
        _t("hierarchical-selection", "Hierarchical Selection", "Seleziona prima il documento, poi i suoi chunk.", "design", tags="selection hierarchical"),
        _t("context-window-packing", "Context Window Packing", "Impacchetta i chunk selezionati nella finestra del prompt.", "reference", "build_context", "selection packing context"),
        _t("rerank-then-select", "Rerank-then-select", "Riordina un pool ampio prima di tagliare a K.", "design", tags="selection two-stage rerank"),
        _t("evidence-selection", "Evidence Selection", "Seleziona solo i passaggi che supportano una risposta.", "reference", "select_evidence", "selection evidence groundedness"),
        _t("redundancy-penalty", "Redundancy Penalty", "Riduce il punteggio di chunk molto simili tra loro.", "reference", "penalize_redundancy", "selection redundancy"),
        _t("minimum-relevance-threshold", "Minimum Relevance Threshold", "Scarta tutti i candidati sotto la soglia minima.", "reference", "filter_candidates", "selection relevance threshold"),
        _t("adaptive-token-budget", "Adaptive Token Budget", "Regola il budget in base alla complessità della query.", "design", tags="selection adaptive tokens"),
    ),
)

_CONTEXT = _group(
    "Context Processing",
    PHASES[8],
    (
        _t("context-expansion", "Context Expansion", "Aggiunge passaggi circostanti ai chunk selezionati.", "reference", "expand_context", "context expansion window", "window=1"),
        _t("context-compression", "Context Compression", "Comprime il contesto riducendo token e rumore.", "reference", "compress_context", "context compression", "ratio=0.5"),
        _t("llmlingua", "LLMLingua", "Comprime prompt con un modello small di compressione.", "provider", tags="context compression llm"),
        _t("longllmlingua", "LongLLMLingua", "Compressione specifica per contesti lunghi.", "provider", tags="context compression long-context"),
        _t("selective-context", "Selective Context", "Mantiene solo le informazioni più informative del contesto.", "provider", tags="context compression selective"),
        _t("recomp", "RECOMP", "Compressore addestrato con contrasto per RAG.", "provider", tags="context compression trained"),
        _t("filco", "FILCO", "Filtra il contesto con un modello addestrato per la fedeltà.", "provider", tags="context compression filtering"),
        _t("map-reduce-summarization", "Map-Reduce Summarization", "Riassume i chunk e poi combina i riassunti.", "provider", tags="context summarization map-reduce"),
        _t("refine-summarization", "Refine Summarization", "Aggiorna iterativamente un riassunto con nuovi chunk.", "provider", tags="context summarization iterative"),
        _t("tree-summarization", "Tree Summarization", "Costruisce un albero di riassunti ricorsivi.", "provider", tags="context summarization tree"),
        _t("lost-in-the-middle-mitigation", "Lost-in-the-middle Mitigation", "Ridistribuisce le prove importanti nel prompt.", "reference", "reorder_context", "context positioning llm"),
        _t("fusion-in-decoder", "Fusion-in-Decoder", "Codifica ogni passaggio separatamente e fonde nel decoder.", "provider", tags="context fid generation"),
        _t("evidence-alignment", "Evidence Alignment", "Allinea ogni affermazione al passaggio che la supporta.", "reference", "align_evidence", "context evidence citation"),
        _t("context-reordering", "Context Reordering", "Ordina i chunk per rilevanza e posizione nel documento.", "reference", "reorder_context", "context ordering"),
        _t("context-packaging", "Context Packaging", "Formatta i chunk in sezioni leggibili per il prompt.", "reference", "build_context", "context formatting prompt"),
        _t("context-deduplication", "Context Deduplication", "Rimuove ripetizioni interne al contesto finale.", "reference", "dedupe_context", "context dedup"),
        _t("multi-hop-stitching", "Multi-hop Stitching", "Cuce insieme prove provenienti da più passaggi.", "design", tags="context multihop reasoning"),
        _t("prompt-truncation", "Prompt Truncation", "Tronca il contesto rispettando il limite del modello.", "reference", "truncate_context", "context truncation", "max_tokens=4000"),
        _t("context-budgeting", "Context Budgeting", "Ripartisce il budget tra istruzioni, storico e prove.", "reference", "budget_context", "context tokens budget"),
        _t("citation-injection", "Citation Injection", "Inserisce marcatori di citazione accanto alle prove.", "reference", "inject_citations", "context citation grounding"),
        _t("context-quality-filtering", "Context Quality Filtering", "Rimuove dal contesto chunk di bassa qualità.", "reference", "filter_context", "context quality"),
        _t("structured-context-formatting", "Structured Context Formatting", "Usa XML o JSON per delimitare le sezioni del contesto.", "reference", "build_context", "context structured format"),
        _t("context-window-management", "Context Window Management", "Gestisce la finestra disponibile tra turni di conversazione.", "design", tags="context memory long-context"),
        _t("sentence-window-context", "Sentence Window Context", "Mostra la frase chiave con il vicinato immediato.", "reference", "sentence_window_chunks", "context window sentences"),
    ),
)

_GENERATION = _group(
    "Generation",
    PHASES[9],
    (
        _t("zero-shot-generation", "Zero-shot Generation", "Genera una risposta senza esempi aggiuntivi.", "provider", "generate_answer", "generation zeroshot"),
        _t("few-shot-generation", "Few-shot Generation", "Fornisce esempi di risposte nel prompt.", "provider", tags="generation fewshot prompt"),
        _t("chain-of-thought", "Chain-of-Thought", "Chiede all'LLM di mostrare il ragionamento passo passo.", "provider", tags="generation cot reasoning"),
        _t("react-generation", "ReAct Generation", "Alterna ragionamento, azioni e osservazioni.", "provider", tags="generation react agent tools"),
        _t("self-consistency", "Self-consistency", "Campiona più risposte e sceglie il consenso maggiore.", "provider", tags="generation sampling reasoning", parameters="samples=5"),
        _t("structured-json-output", "Structured JSON Output", "Forza un output JSON conforme a uno schema.", "provider", "generate_structured", "generation json schema"),
        _t("citation-aware-generation", "Citation-aware Generation", "Genera risposte con citazioni alle fonti recuperate.", "provider", tags="generation citation grounding"),
        _t("tree-of-thoughts", "Tree-of-Thoughts", "Esplora più rami di ragionamento e li valuta.", "provider", tags="generation tot reasoning"),
        _t("graph-of-thoughts", "Graph-of-Thoughts", "Collega pensieri in un grafo di ragionamento.", "provider", tags="generation got reasoning"),
        _t("constrained-decoding", "Constrained Decoding", "Limita la generazione a token o grammatiche ammesse.", "provider", tags="generation decoding grammar"),
        _t("grounded-generation", "Grounded Generation", "Vincola la risposta alle sole prove recuperate.", "design", tags="generation grounding faithfulness"),
        _t("extractive-generation", "Extractive Generation", "Costruisce la risposta copiando frasi dal contesto.", "reference", "generate_extractive", "generation extractive deterministic"),
        _t("abstractive-generation", "Abstractive Generation", "Riformula le informazioni con linguaggio nuovo.", "provider", tags="generation abstractive llm"),
        _t("temperature-sampling", "Temperature Sampling", "Controlla la casualità della generazione.", "provider", tags="generation sampling decoding", parameters="temperature=0.2"),
        _t("beam-search", "Beam Search", "Mantiene più ipotesi durante la decodifica.", "provider", tags="generation decoding beam", parameters="beams=4"),
        _t("self-refine", "Self-refine", "Genera, critica e migliora la risposta in più passi.", "provider", tags="generation refinement llm"),
        _t("raft", "RAFT", "Addestra il modello a ignorare documenti non rilevanti.", "provider", tags="generation finetuning retrieval"),
        _t("chain-of-note", "Chain-of-Note", "Annota la rilevanza di ogni documento prima di rispondere.", "provider", tags="generation reasoning evidence"),
        _t("answer-format-validation", "Answer Format Validation", "Verifica che la risposta rispetti il formato richiesto.", "reference", "validate_answer_format", "generation validation schema"),
        _t("streaming-generation", "Streaming Generation", "Trasmette i token della risposta progressivamente.", "integration", tags="generation streaming sse"),
        _t("tool-augmented-generation", "Tool-augmented Generation", "Chiama strumenti esterni durante la generazione.", "design", tags="generation tools agent"),
        _t("retrieval-grounded-prompt", "Retrieval-grounded Prompt", "Costruisce il prompt con istruzioni e prove recuperate.", "reference", "build_prompt", "generation prompt grounding"),
        _t("multi-document-synthesis", "Multi-document Synthesis", "Sintetizza una risposta coerente da più fonti.", "provider", tags="generation synthesis multidoc"),
        _t("refusal-generation", "Refusal Generation", "Rifiuta di rispondere quando le prove sono insufficienti.", "provider", tags="generation abstention safety"),
        _t("code-generation", "Code Generation", "Produce codice a partire da documentazione recuperata.", "provider", tags="generation code llm"),
        _t("sql-generation", "SQL Generation", "Genera query SQL a partire da linguaggio naturale.", "provider", tags="generation sql database"),
        _t("multilingual-generation", "Multilingual Generation", "Genera la risposta nella lingua della query.", "provider", tags="generation multilingual"),
        _t("template-generation", "Template-based Generation", "Compila un template deterministico con le prove.", "reference", "generate_answer", "generation template deterministic"),
    ),
)

_VALIDATION = _group(
    "Validation",
    PHASES[10],
    (
        _t("groundedness-verification", "Groundedness Verification", "Verifica che la risposta sia supportata dal contesto.", "reference", "verify_groundedness", "validation grounding faithfulness", "threshold=0.7"),
        _t("nli-verification", "NLI Verification", "Usa natural language inference per verificare le affermazioni.", "provider", tags="validation nli entailment"),
        _t("llm-as-a-judge", "LLM-as-a-Judge", "Un LLM valuta la qualità della risposta.", "provider", tags="validation judge llm"),
        _t("self-critique", "Self-critique", "Il modello critica e corregge la propria risposta.", "provider", tags="validation self-reflection llm"),
        _t("citation-validation", "Citation Validation", "Controlla che ogni citazione punti a una fonte reale.", "reference", "validate_citations", "validation citation provenance"),
        _t("pydantic-schema-validation", "Pydantic Schema Validation", "Valida la struttura dell'output con Pydantic.", "reference", "validate_schema", "validation pydantic schema"),
        _t("pii-detection", "PII Detection", "Rileva dati personali nella risposta generata.", "reference", "detect_pii", "validation privacy security"),
        _t("hallucination-detection", "Hallucination Detection", "Rileva contenuti non supportati dalle fonti.", "provider", tags="validation hallucination llm"),
        _t("fallback-strategy", "Fallback Strategy", "Restituisce una risposta sicura quando la validazione fallisce.", "reference", "fallback_answer", "validation fallback safety"),
        _t("answer-relevance-check", "Answer Relevance Check", "Verifica che la risposta affronti la domanda.", "provider", tags="validation relevance judge"),
        _t("faithfulness-scoring", "Faithfulness Scoring", "Calcola un punteggio di fedeltà al contesto.", "provider", tags="validation faithfulness metric"),
        _t("claim-verification", "Claim Verification", "Verifica singole affermazioni contro le prove.", "provider", tags="validation claims grounding"),
        _t("confidence-scoring", "Confidence Scoring", "Stima la confidenza della risposta finale.", "reference", "score_confidence", "validation confidence"),
        _t("human-in-the-loop", "Human-in-the-loop", "Invia le risposte dubbie a un revisore umano.", "design", tags="validation human review"),
        _t("consistency-check", "Consistency Check", "Controlla contraddizioni interne nella risposta.", "reference", "check_consistency", "validation consistency"),
        _t("toxicity-check", "Toxicity Check", "Rileva contenuti tossici o inappropriati.", "provider", tags="validation safety moderation"),
        _t("factuality-check", "Factuality Check", "Verifica i fatti rispetto a fonti autorevoli.", "provider", tags="validation factuality llm"),
        _t("rule-based-validation", "Rule-based Validation", "Applica regole deterministiche all'output.", "reference", "validate_rules", "validation rules deterministic"),
        _t("answer-completeness-check", "Answer Completeness Check", "Verifica che tutti i punti della domanda siano coperti.", "provider", tags="validation completeness judge"),
        _t("citation-coverage-check", "Citation Coverage Check", "Verifica che le affermazioni chiave abbiano citazioni.", "reference", "validate_citation_coverage", "validation citation coverage"),
        _t("refusal-detection", "Refusal Detection", "Rileva rifiuti indebiti o eccessivi del modello.", "reference", "detect_refusal", "validation abstention"),
        _t("source-attribution-check", "Source Attribution Check", "Controlla che ogni fonte citata sia retrieval-effective.", "reference", "validate_sources", "validation attribution provenance"),
        _t("cross-answer-agreement", "Cross-answer Agreement", "Confronta più risposte per rilevare incoerenze.", "reference", "check_agreement", "validation consistency ensemble"),
        _t("safety-filter", "Safety Filter", "Blocca risposte che violano le policy di sicurezza.", "provider", tags="validation safety guardrails"),
        _t("validation-retry-loop", "Validation Retry Loop", "Rigenera la risposta finché la validazione non passa.", "design", tags="validation retry orchestration"),
        _t("deterministic-answer-check", "Deterministic Answer Check", "Confronta la risposta con valori attesi noti.", "reference", "check_expected_answer", "validation deterministic testing"),
    ),
)

_FEEDBACK = _group(
    "Orchestration",
    PHASES[11],
    (
        _t("explicit-feedback", "Explicit Feedback", "Raccoglie valutazioni esplicite degli utenti.", "design", tags="feedback explicit rating"),
        _t("implicit-feedback", "Implicit Feedback", "Inferisce preferenze da clic, tempo di lettura e riformulazioni.", "design", tags="feedback implicit behavior"),
        _t("hard-negative-mining", "Hard Negative Mining", "Seleziona esempi negativi difficili per l'addestramento.", "reference", "mine_hard_negatives", "feedback training negatives"),
        _t("episodic-memory", "Episodic Memory", "Memorizza interazioni passate con contesto temporale.", "design", tags="memory episodic conversation"),
        _t("semantic-memory", "Semantic Memory", "Conserva fatti e conoscenze astratte apprese.", "design", tags="memory semantic facts"),
        _t("working-memory", "Working Memory", "Mantiene lo stato della conversazione corrente.", "design", tags="memory working session"),
        _t("long-term-memory", "Long-term Memory", "Persiste informazioni tra sessioni diverse.", "integration", tags="memory long-term persistence"),
        _t("rlhf", "RLHF", "Allinea il modello con feedback umano tramite RL.", "provider", tags="feedback rlhf alignment"),
        _t("dpo", "DPO", "Direct Preference Optimization su coppie di preferenze.", "provider", tags="feedback dpo alignment"),
        _t("active-learning", "Active Learning", "Seleziona esempi da etichettare con massimo guadagno.", "design", tags="feedback active-learning labeling"),
        _t("online-learning", "Online Learning", "Aggiorna il modello con il feedback in tempo reale.", "design", tags="feedback online adaptation"),
        _t("feedback-loop", "Feedback Loop", "Collega le valutazioni alle configurazioni della pipeline.", "design", tags="feedback loop continuous-improvement"),
        _t("preference-optimization", "Preference Optimization", "Ottimizza il ranking usando preferenze relative.", "provider", tags="feedback preferences ranking"),
        _t("reward-modeling", "Reward Modeling", "Addestra un modello che stima la qualità delle risposte.", "provider", tags="feedback reward-model ltr"),
        _t("negative-cache", "Negative Cache", "Evita di recuperare ripetutamente documenti giudicati irrilevanti.", "design", tags="feedback caching negatives"),
        _t("continuous-index-refresh", "Continuous Index Refresh", "Aggiorna indicizzazione e metadati dopo il feedback.", "design", tags="feedback index maintenance"),
        _t("user-feedback-capture", "User Feedback Capture", "Registra like, dislike e commenti sugli output.", "integration", tags="feedback telemetry storage"),
        _t("query-log-mining", "Query Log Mining", "Analizza i log delle query per scoprire lacune.", "reference", "mine_query_logs", "feedback logs analytics"),
    ),
)

_ORCHESTRATION = _group(
    "Orchestration",
    PHASES[12],
    (
        _t("naive-rag", "Naive RAG", "Indicizza, recupera e genera in un solo flusso lineare.", "reference", "orchestrate", "orchestration naive baseline"),
        _t("advanced-rag", "Advanced RAG", "Aggiunge Preretrieving e postprocessing al flusso base.", "reference", "orchestrate", "orchestration advanced pipeline"),
        _t("modular-rag", "Modular RAG", "Compone moduli indipendenti sostituibili.", "reference", "orchestrate", "orchestration modular"),
        _t("adaptive-rag", "Adaptive RAG", "Sceglie la strategia in base alla complessità della query.", "reference", "orchestrate", "orchestration adaptive routing"),
        _t("crag", "CRAG", "Valuta i risultati e attiva recupero correttivo o web.", "reference", "orchestrate", "orchestration crag corrective"),
        _t("self-rag", "Self-RAG", "Il modello riflette su quando recuperare e come valutare.", "provider", tags="orchestration self-rag reflection"),
        _t("agentic-rag", "Agentic RAG", "Un agente pianifica, richiama strumenti e decide quando fermarsi.", "design", tags="orchestration agent tools"),
        _t("iterative-rag", "Iterative RAG", "Ripete recupero e generazione fino a criteri di arresto.", "reference", "orchestrate", "orchestration iterative loop"),
        _t("graphrag", "GraphRAG", "Costruisce ed esplora un grafo di entità e comunità.", "design", "orchestrate_graph", "orchestration graph knowledge"),
        _t("multimodal-rag", "Multimodal RAG", "Recupera e genera usando testo, immagini e audio.", "provider", tags="orchestration multimodal vision"),
        _t("multi-agent-rag", "Multi-Agent RAG", "Coordina più agenti specializzati nella pipeline.", "design", tags="orchestration multi-agent"),
        _t("long-context-rag", "Long-context RAG", "Sfrutta una finestra estesa riducendo i passaggi di retrieval.", "design", tags="orchestration long-context"),
        _t("flare", "FLARE", "Attiva il recupero quando il modello è incerto durante la generazione.", "provider", tags="orchestration flare active retrieval"),
        _t("ircot", "IRCoT", "Intreccia recupero e catena di ragionamento.", "provider", tags="orchestration ircot reasoning"),
        _t("dragin", "DRAGIN", "Recupera dinamicamente in base all'incertezza dei token.", "provider", tags="orchestration dragin dynamic"),
        _t("search-r1", "Search-R1", "Addestra un agente a cercare con reinforcement learning.", "provider", tags="orchestration search-r1 rl"),
        _t("rag-fusion", "RAG-Fusion", "Genera più query, recupera e fonde i risultati.", "reference", "orchestrate", "orchestration rag-fusion multi-query"),
        _t("raptor-orchestration", "RAPTOR Orchestration", "Recupera da più livelli dell'albero di riassunti.", "design", tags="orchestration raptor tree"),
        _t("longrag", "LongRAG", "Usa unità lunghe per ridurre il numero di candidati.", "design", tags="orchestration longrag long-context"),
        _t("memory-augmented-rag", "Memory-augmented RAG", "Integra memoria persistente nella pipeline di recupero.", "design", tags="orchestration memory persistent"),
        _t("speculative-rag", "Speculative RAG", "Genera bozze multiple e le verifica rapidamente.", "design", tags="orchestration speculative drafting"),
        _t("self-ask", "Self-ask", "L'LLM si pone domande successive prima di rispondere.", "provider", tags="orchestration self-ask reasoning"),
        _t("query-router-pipeline", "Query Router Pipeline", "Smista le richieste verso pipeline specializzate.", "reference", "orchestrate", "orchestration router pipeline"),
        _t("conditional-branching", "Conditional Branching", "Esegue rami diversi in base a condizioni sullo stato.", "reference", "orchestrate", "orchestration conditional graph"),
        _t("parallel-retrieval", "Parallel Retrieval", "Esegue più retriever in parallelo per ridurre la latenza.", "design", tags="orchestration parallel performance"),
        _t("pipeline-dsl", "Pipeline DSL", "Descrive la pipeline come grafo dichiarativo configurabile.", "design", tags="orchestration dsl configuration"),
        _t("recursive-rag-orchestration", "Recursive RAG", "Applica ricorsivamente recupero e sintesi sui risultati.", "design", tags="orchestration recursive"),
        _t("reflective-rag", "Reflective RAG", "Valuta e corregge il proprio piano di recupero.", "design", tags="orchestration reflection planning"),
        _t("plan-and-execute", "Plan-and-Execute", "Pianifica le azioni e poi le esegue con strumenti.", "provider", tags="orchestration planning agent"),
        _t("tool-augmented-rag", "Tool-augmented RAG", "Integra API e strumenti esterni nel flusso RAG.", "design", tags="orchestration tools integration"),
        _t("hierarchical-agent-rag", "Hierarchical Agent RAG", "Organizza agenti supervisor e sub-agenti specializzati.", "design", tags="orchestration agents hierarchy"),
    ),
)

_EVALUATION = _group(
    "Evaluation",
    PHASES[10],
    (
        _t("chunk-quality-evaluation", "Chunk Quality Evaluation", "Valuta la qualità dei chunk prodotti dal parser.", "reference", "evaluate_chunks", "evaluation chunking quality"),
        _t("embedding-evaluation", "Embedding Evaluation", "Misura la qualità dello spazio vettoriale per il retrieval.", "design", tags="evaluation embedding retrieval"),
        _t("precision-at-k", "Precision@K", "Frazione di risultati rilevanti nei primi K.", "reference", "precision_at_k", "evaluation metric retrieval", "k=5"),
        _t("recall-at-k", "Recall@K", "Frazione di documenti rilevanti trovati nei primi K.", "reference", "recall_at_k", "evaluation metric retrieval", "k=5"),
        _t("hit-rate", "Hit Rate", "Indica se almeno un documento rilevante è nei primi K.", "reference", "hit_rate_at_k", "evaluation metric retrieval", "k=5"),
        _t("mrr", "Mean Reciprocal Rank", "Media dell'inverso del rango della prima risposta corretta.", "reference", "mean_reciprocal_rank", "evaluation metric ranking"),
        _t("map", "Mean Average Precision", "Media della precisione media sui documenti rilevanti.", "reference", "average_precision", "evaluation metric ranking"),
        _t("ndcg", "NDCG", "Qualità del ranking con guadagno scontato per posizione.", "reference", "ndcg_at_k", "evaluation metric ranking", "k=5"),
        _t("success-at-k", "Success@K", "Verifica se la risposta corretta compare entro K risultati.", "reference", "success_at_k", "evaluation metric retrieval", "k=5"),
        _t("coverage-metric", "Coverage", "Quota di query coperte da almeno una fonte rilevante.", "reference", "coverage", "evaluation metric retrieval"),
        _t("reranking-metrics", "Reranking Metrics", "Valuta la qualità del riordinamento rispetto al ranking iniziale.", "reference", "evaluate_reranking", "evaluation reranking metrics"),
        _t("ragas", "RAGAS", "Framework di valutazione faithfulness e relevance.", "integration", tags="evaluation framework llm"),
        _t("ares", "ARES", "Framework di valutazione automatica con judge addestrato.", "integration", tags="evaluation framework judge"),
        _t("trulens", "TruLens", "Telemetria e valutazione della qualità RAG.", "integration", tags="evaluation framework monitoring"),
        _t("deepeval", "DeepEval", "Suite di metriche unitarie per pipeline LLM.", "integration", tags="evaluation framework metrics"),
        _t("ragchecker", "RAGChecker", "Diagnostica fine-grained di retrieval e generazione.", "integration", tags="evaluation framework diagnostics"),
        _t("langsmith", "LangSmith", "Tracciamento e confronto delle corse di valutazione.", "integration", tags="evaluation framework observability"),
        _t("robustness-evaluation", "Robustness Evaluation", "Testa la pipeline con query rumorose o avversarie.", "design", tags="evaluation robustness adversarial"),
        _t("performance-evaluation", "Performance Evaluation", "Misura latenza, throughput e costo per query.", "reference", "evaluate_performance", "evaluation performance latency"),
        _t("faithfulness-metric", "Faithfulness Metric", "Misura quanto la risposta è supportata dal contesto.", "provider", tags="evaluation metric llm"),
        _t("answer-relevance-metric", "Answer Relevance Metric", "Misura quanto la risposta è pertinente alla query.", "provider", tags="evaluation metric llm"),
        _t("context-precision", "Context Precision", "Misura la frazione di contesto rilevante.", "provider", tags="evaluation metric context"),
        _t("context-recall", "Context Recall", "Misura quanto contesto rilevante è stato recuperato.", "provider", tags="evaluation metric context"),
        _t("latency-benchmark", "Latency Benchmark", "Misura i tempi delle singole fasi della pipeline.", "reference", "benchmark_latency", "evaluation performance benchmark"),
        _t("cost-benchmark", "Cost Benchmark", "Stima il costo per query di provider e risorse.", "reference", "benchmark_cost", "evaluation performance cost"),
        _t("golden-dataset-evaluation", "Golden Dataset Evaluation", "Valuta contro un dataset di domande e risposte attese.", "design", tags="evaluation dataset benchmark"),
        _t("adversarial-evaluation", "Adversarial Evaluation", "Usa input ostili per verificare la robustezza.", "design", tags="evaluation adversarial security"),
        _t("regression-testing", "Regression Testing", "Verifica che nuove configurazioni non peggiorino le metriche.", "design", tags="evaluation regression ci"),
        _t("human-evaluation", "Human Evaluation", "Valutazione manuale di campioni di risposte.", "design", tags="evaluation human review"),
        _t("offline-online-evaluation", "Offline/Online Evaluation", "Confronta metriche offline con comportamento in produzione.", "design", tags="evaluation production ab"),
        _t("ablation-study", "Ablation Study", "Disattiva singoli moduli per misurarne il contributo.", "design", tags="evaluation ablation analysis"),
    ),
)

_SECURITY = _group(
    "Monitoring & Security",
    PHASES[13],
    (
        _t("pii-redaction-policy", "PII Redaction Policy", "Applica policy di anonimizzazione a indicizzazione e output.", "design", tags="security privacy pii"),
        _t("tenant-isolation", "Tenant Isolation", "Separa indici e dati tra tenant diversi.", "design", tags="security multitenancy isolation"),
        _t("rbac", "RBAC", "Controllo degli accessi basato sui ruoli.", "design", tags="security authorization roles", parameters="roles=admin,user"),
        _t("abac", "ABAC", "Controllo degli accessi basato su attributi e policy.", "design", tags="security authorization attributes"),
        _t("prompt-injection-defense", "Prompt Injection Defense", "Rileva istruzioni malevole negli input utente.", "design", tags="security prompt-injection llm"),
        _t("indirect-injection-defense", "Indirect Injection Defense", "Filtra istruzioni nascoste nei documenti recuperati.", "design", tags="security indirect-injection documents"),
        _t("retrieval-poisoning-defense", "Retrieval Poisoning Defense", "Impedisce l'inserimento di contenuti che manipolano il ranking.", "design", tags="security poisoning index"),
        _t("provenance-tracking", "Provenance Tracking", "Registra sorgente e versione di ogni informazione usata.", "reference", "track_provenance", "security provenance audit"),
        _t("audit-logging", "Audit Logging", "Registra chi accede a quali documenti e risposte.", "reference", "audit_log", "security audit compliance"),
        _t("access-control-filter", "Access Control Filter", "Filtra i risultati in base ai permessi dell'utente.", "design", tags="security access-control retrieval"),
        _t("encryption-at-rest", "Encryption at Rest", "Cifra documenti e vettori memorizzati.", "integration", tags="security encryption storage"),
        _t("encryption-in-transit", "Encryption in Transit", "Protegge le comunicazioni con TLS.", "integration", tags="security encryption network"),
        _t("secrets-management", "Secrets Management", "Gestisce chiavi e credenziali in un vault.", "integration", tags="security secrets vault"),
        _t("data-retention-policy", "Data Retention Policy", "Definisce la conservazione e la cancellazione dei dati.", "design", tags="security governance retention"),
        _t("input-sanitization", "Input Sanitization", "Rimuove costrutti pericolosi dagli input.", "reference", "sanitize_input", "security sanitization"),
        _t("output-sanitization", "Output Sanitization", "Rimuove contenuti pericolosi dalle risposte.", "reference", "sanitize_output", "security sanitization"),
        _t("prompt-guardrails", "Prompt Guardrails", "Applica regole e filtri prima e dopo il modello.", "design", tags="security guardrails llm"),
        _t("source-allowlist", "Source Allowlist", "Limita le fonti recuperabili a un elenco approvato.", "reference", "filter_allowed_sources", "security allowlist sources"),
        _t("data-lineage", "Data Lineage", "Traccia il percorso dei dati dal sorgente alla risposta.", "reference", "track_lineage", "security provenance governance"),
        _t("gdpr-compliance", "GDPR Compliance", "Supporta diritti di accesso, rettifica e cancellazione.", "design", tags="security compliance privacy"),
        _t("row-level-security", "Row-level Security", "Applica filtri di sicurezza a livello di riga nel DB.", "design", tags="security database rls"),
        _t("security-scanning", "Security Scanning", "Analizza dipendenze e configurazioni per vulnerabilità.", "integration", tags="security scanning devsecops"),
    ),
)

_OBSERVABILITY = _group(
    "Monitoring & Security",
    PHASES[14],
    (
        _t("distributed-tracing", "Distributed Tracing", "Traccia una richiesta attraverso tutti i servizi.", "integration", tags="observability tracing telemetry"),
        _t("exact-cache", "Exact Cache", "Riutilizza la risposta per query identiche.", "reference", "cache_exact", "caching exact performance"),
        _t("semantic-cache", "Semantic Cache", "Riutilizza risposte per query semanticamente simili.", "reference", "cache_semantic", "caching semantic embedding", "threshold=0.95"),
        _t("embedding-cache", "Embedding Cache", "Memorizza gli embedding per testi già visti.", "reference", "cache_embeddings", "caching embedding performance"),
        _t("result-cache", "Result Cache", "Memorizza i risultati intermedi delle fasi della pipeline.", "reference", "cache_results", "caching results stages"),
        _t("ab-testing", "A/B Testing", "Confronta due configurazioni su traffico reale.", "design", tags="observability experimentation ab"),
        _t("canary-release", "Canary Release", "Distribuisce una nuova configurazione a una piccola quota di traffico.", "design", tags="observability deployment canary"),
        _t("replay-testing", "Replay Testing", "Riesegue richieste registrate per confronto.", "design", tags="observability replay regression"),
        _t("experiment-tracking", "Experiment Tracking", "Registra parametri, metriche e artefatti degli esperimenti.", "integration", tags="observability experiments tracking"),
        _t("drift-detection", "Drift Detection", "Rileva cambiamenti nella distribuzione dei dati.", "design", tags="observability drift monitoring"),
        _t("cost-monitoring", "Cost Monitoring", "Monitora il costo di provider e infrastruttura.", "reference", "monitor_cost", "observability cost metrics"),
        _t("latency-monitoring", "Latency Monitoring", "Traccia la latenza per fase della pipeline.", "reference", "monitor_latency", "observability latency metrics"),
        _t("error-rate-monitoring", "Error Rate Monitoring", "Monitora errori e fallimenti per fase.", "reference", "monitor_errors", "observability errors metrics"),
        _t("metric-dashboards", "Metric Dashboards", "Visualizza le metriche operative in dashboards.", "integration", tags="observability dashboards metrics"),
        _t("alerting", "Alerting", "Notifica quando le soglie operative vengono superate.", "integration", tags="observability alerts on-call"),
        _t("rate-limiting", "Rate Limiting", "Limita il numero di richieste per utente o tenant.", "integration", tags="observability reliability limits", parameters="rpm=60"),
        _t("anomaly-detection", "Anomaly Detection", "Individua comportamenti anomali nei log e nelle metriche.", "design", tags="observability anomalies ml"),
        _t("slo-monitoring", "SLO Monitoring", "Verifica il rispetto degli obiettivi di livello servizio.", "design", tags="observability slo reliability"),
        _t("profile-tracing", "Profile Tracing", "Profilizza CPU e memoria delle fasi locali.", "reference", "profile_pipeline", "observability profiling performance"),
        _t("token-accounting", "Token Accounting", "Conta i token consumati da prompt e risposte.", "reference", "count_tokens", "observability tokens cost"),
        _t("pipeline-versioning", "Pipeline Versioning", "Associa ogni esecuzione a una versione della pipeline.", "design", tags="observability versioning reproducibility"),
        _t("log-aggregation", "Log Aggregation", "Centralizza i log di tutti i componenti.", "integration", tags="observability logs centralization"),
        _t("feedback-telemetry", "Feedback Telemetry", "Correla i feedback utente con le esecuzioni.", "design", tags="observability feedback analytics"),
    ),
)

_GROUPS = (
    _DATA_SOURCES,
    _PARSING,
    _PREPROCESSING,
    _CHUNKING,
    _ENRICHMENT,
    _EMBEDDINGS,
    _INDEXING,
    _QUERY,
    _RETRIEVAL,
    _FUSION,
    _RERANKING,
    _SELECTION,
    _CONTEXT,
    _GENERATION,
    _VALIDATION,
    _FEEDBACK,
    _ORCHESTRATION,
    _EVALUATION,
    _SECURITY,
    _OBSERVABILITY,
)

TECHNIQUES: tuple[Technique, ...] = tuple(
    technique for group in _GROUPS for technique in group
)
"""Catalogo completo, ordinato per categoria e fase."""

if len({technique.id for technique in TECHNIQUES}) != len(TECHNIQUES):
    raise ValueError("IDs duplicati nel catalogo delle tecniche")

if any(technique.category not in CATEGORIES for technique in TECHNIQUES):
    raise ValueError("Categoria non valida nel catalogo delle tecniche")

if any(technique.phase not in PHASES for technique in TECHNIQUES):
    raise ValueError("Fase non valida nel catalogo delle tecniche")

_BY_ID: dict[str, Technique] = {technique.id.casefold(): technique for technique in TECHNIQUES}


def _resolve_phase(value: str | int) -> str | None:
    """Accetta numero, slug o nome della fase e restituisce il nome canonico."""
    key = _slug(str(value))
    for phase in PHASES:
        if key in {phase_slug(phase), _slug(phase), phase.split(" ", 1)[0]}:
            return phase
    return None


def _resolve_category(value: str) -> str | None:
    """Accetta slug o nome della categoria e restituisce il nome canonico."""
    key = _slug(value)
    for category in CATEGORIES:
        if key == category_slug(category):
            return category
    return None


def list_techniques(
    phase: str | int | None = None,
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> tuple[Technique, ...]:
    """Filtra il catalogo per fase, categoria, stato e testo libero (AND logico)."""
    wanted_phase = _resolve_phase(phase) if phase is not None else None
    wanted_category = _resolve_category(category) if category is not None else None
    wanted_status = status.casefold() if status is not None else None
    needle = _slug(search) if search else ""

    if phase is not None and wanted_phase is None:
        return ()
    if category is not None and wanted_category is None:
        return ()
    if wanted_status is not None and wanted_status not in STATUSES:
        return ()

    result: list[Technique] = []
    for technique in TECHNIQUES:
        if wanted_phase and technique.phase != wanted_phase:
            continue
        if wanted_category and technique.category != wanted_category:
            continue
        if wanted_status and technique.status != wanted_status:
            continue
        if needle:
            haystack = _slug(
                " ".join(
                    (
                        technique.id,
                        technique.name,
                        technique.description,
                        " ".join(technique.tags),
                        technique.implementation or "",
                    )
                )
            )
            if needle not in haystack:
                continue
        result.append(technique)
    return tuple(result)


def get_technique(id: str) -> Technique | None:
    """Restituisce una tecnica dal suo ID slug, oppure ``None``."""
    return _BY_ID.get(id.casefold())


def catalog_summary() -> dict[str, Any]:
    """Restituisce conteggi aggregati per stato, categoria e fase."""
    return {
        "total": len(TECHNIQUES),
        "by_status": {
            name: sum(1 for technique in TECHNIQUES if technique.status == name)
            for name in STATUSES
        },
        "by_category": {
            name: sum(1 for technique in TECHNIQUES if technique.category == name)
            for name in CATEGORIES
        },
        "by_phase": {
            name: sum(1 for technique in TECHNIQUES if technique.phase == name)
            for name in PHASES
        },
    }









