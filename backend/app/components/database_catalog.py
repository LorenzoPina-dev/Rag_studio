"""Catalogo dichiarativo dei database collegabili dalle pipeline.

Ogni database è descritto una sola volta: nome, famiglia, porta/protocollo
predefiniti, host Docker, percorso locale e campi richiesti. Da questa
descrizione derivano:

* le definizioni dei nodi (un nodo per tipo di database);
* i campi che la UI deve chiedere (quelli non derivabili dal tipo e dalla
  modalità di connessione);
* la configurazione di connessione effettiva (URL/DSN inclusi), senza
  dipendere da SDK specifici.

Il modulo è puro: nessuna rete, nessun file, nessuna dipendenza da FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DatabaseFamily(str, Enum):
    VECTOR = "vector"
    RELATIONAL = "relational"
    DOCUMENT = "document"
    SEARCH = "search"
    CACHE = "cache"
    GRAPH = "graph"
    TIME_SERIES = "time-series"


class ConnectionMode(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class ConnectionTarget(str, Enum):
    """Dove gira il database: file/processo locale, localhost, Docker o IP."""

    EMBEDDED = "embedded"
    LOCALHOST = "localhost"
    DOCKER = "docker"
    IP = "ip"


class FieldKind(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    PASSWORD = "password"
    SELECT = "select"
    PATH = "path"


@dataclass(frozen=True)
class FieldSpec:
    """Campo richiesto all'utente, con regole di visibilità dichiarative."""

    key: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    required: bool = True
    default: str | int | None = None
    options: tuple[str, ...] = ()
    help: str = ""
    modes: tuple[ConnectionMode, ...] | None = None
    targets: tuple[ConnectionTarget, ...] | None = None
    derived: bool = False
    visible_when: dict[str, Any] | None = None

    def visible_for(self, mode: ConnectionMode, target: ConnectionTarget) -> bool:
        if self.modes is not None and mode not in self.modes:
            return False
        return self.targets is None or target in self.targets


@dataclass(frozen=True)
class DatabaseSpec:
    """Descrizione di un database e dei suoi valori derivabili."""

    id: str
    name: str
    family: DatabaseFamily
    description: str
    accent: str
    default_port: int | None = None
    scheme: str = ""
    docker_host: str = "localhost"
    embedded_path: str | None = None
    health_path: str | None = None
    default_container: str | None = None
    collection_label: str | None = None
    default_collection: str | None = None
    auth: bool = False
    token: bool = False
    database: bool = False
    supports_embedded: bool = False
    supports_remote: bool = True
    extra_fields: tuple[FieldSpec, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def supports_local(self) -> bool:
        return self.supports_embedded or self.supports_remote

    def targets_for(self, mode: ConnectionMode) -> tuple[ConnectionTarget, ...]:
        if mode is ConnectionMode.LOCAL:
            targets = []
            if self.supports_embedded:
                targets.append(ConnectionTarget.EMBEDDED)
            if self.supports_remote:
                targets.extend((ConnectionTarget.LOCALHOST, ConnectionTarget.DOCKER))
            return tuple(targets)
        if not self.supports_remote:
            return ()
        return (ConnectionTarget.DOCKER, ConnectionTarget.IP)

    def fields_for(self, mode: ConnectionMode, target: ConnectionTarget) -> list[FieldSpec]:
        """Solo i campi non derivabili: host è chiesto solo per IP."""

        fields: list[FieldSpec] = []
        if target is ConnectionTarget.EMBEDDED:
            fields.append(
                FieldSpec(
                    key="path",
                    label="Percorso locale",
                    kind=FieldKind.PATH,
                    default=self.embedded_path,
                    derived=self.embedded_path is not None,
                    help="File o cartella usata dal database embedded.",
                )
            )
        if target is ConnectionTarget.IP:
            fields.append(
                FieldSpec(
                    key="host",
                    label="IP o hostname",
                    help="Indirizzo del server database raggiungibile dalla rete.",
                )
            )
        if self.default_port is None and target is not ConnectionTarget.EMBEDDED:
            fields.append(FieldSpec(key="port", label="Porta", kind=FieldKind.NUMBER))
        if self.auth and target is not ConnectionTarget.EMBEDDED:
            fields.append(FieldSpec(key="username", label="Utente"))
            fields.append(FieldSpec(key="password", label="Password", kind=FieldKind.PASSWORD))
        if self.token and target is not ConnectionTarget.EMBEDDED:
            fields.append(FieldSpec(key="apiKey", label="API key / token", kind=FieldKind.PASSWORD))
        if self.database and target is not ConnectionTarget.EMBEDDED:
            fields.append(
                FieldSpec(
                    key="database",
                    label="Database",
                    default=self.default_collection,
                    derived=self.default_collection is not None,
                    help="Nome del database/schema da usare.",
                )
            )
        if self.collection_label and target is not ConnectionTarget.EMBEDDED:
            fields.append(
                FieldSpec(
                    key="collection",
                    label=self.collection_label,
                    default=self.default_collection,
                    derived=self.default_collection is not None,
                    help="Nome della collection, tabella o indice.",
                )
            )
        fields.extend(
            item
            for item in self.extra_fields
            if item.visible_for(mode, target) and all(item.key != existing.key for existing in fields)
        )
        return fields


_HEALTH_QDRANT = "/healthz"
_HEALTH_CHROMA = "/api/v1/heartbeat"
_HEALTH_WEAVIATE = "/v1/.well-known/ready"
_HEALTH_OPENSEARCH = "/_cluster/health"


CATALOG: tuple[DatabaseSpec, ...] = (
    # ---------------------------------------------------------------- vector
    DatabaseSpec(
        id="qdrant",
        name="Qdrant",
        family=DatabaseFamily.VECTOR,
        description="Vector database con ricerca ANN e filtri sui payload.",
        accent="#F0B45C",
        default_port=6333,
        scheme="http",
        docker_host="qdrant",
        health_path=_HEALTH_QDRANT,
        collection_label="Collection",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="chroma",
        name="Chroma",
        family=DatabaseFamily.VECTOR,
        description="Vector store embedded o server con API HTTP.",
        accent="#9D7BFF",
        default_port=8000,
        scheme="http",
        docker_host="chroma",
        embedded_path="./.ragstudio/chroma",
        health_path=_HEALTH_CHROMA,
        collection_label="Collection",
        default_collection="documents",
        supports_embedded=True,
    ),
    DatabaseSpec(
        id="milvus",
        name="Milvus",
        family=DatabaseFamily.VECTOR,
        description="Vector database distribuito con indici HNSW/IVF.",
        accent="#4EA8DE",
        default_port=19530,
        scheme="http",
        docker_host="milvus",
        collection_label="Collection",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="weaviate",
        name="Weaviate",
        family=DatabaseFamily.VECTOR,
        description="Vector store con schema, classi e moduli di vettorizzazione.",
        accent="#FF8A65",
        default_port=8080,
        scheme="http",
        docker_host="weaviate",
        health_path=_HEALTH_WEAVIATE,
        collection_label="Class",
        default_collection="Document",
    ),
    DatabaseSpec(
        id="pinecone",
        name="Pinecone",
        family=DatabaseFamily.VECTOR,
        description="Vector database gestito: richiede API key e ambiente.",
        accent="#22C55E",
        default_port=443,
        scheme="https",
        token=True,
        collection_label="Index",
        default_collection="documents",
        supports_remote=True,
        extra_fields=(
            FieldSpec(
                key="environment",
                label="Environment",
                default="us-east-1",
                help="Regione/cloud dell'account Pinecone (es. us-east-1).",
            ),
        ),
    ),
    DatabaseSpec(
        id="faiss",
        name="FAISS (locale)",
        family=DatabaseFamily.VECTOR,
        description="Indice vettoriale locale su file, senza server.",
        accent="#60A5FA",
        embedded_path="./.ragstudio/faiss.index",
        collection_label="Nome indice",
        default_collection="documents",
        supports_embedded=True,
        supports_remote=False,
    ),
    DatabaseSpec(
        id="pgvector",
        name="pgvector",
        family=DatabaseFamily.VECTOR,
        description="Estensione vettoriale di PostgreSQL.",
        accent="#336791",
        default_port=5432,
        scheme="postgresql+psycopg",
        docker_host="postgres",
        auth=True,
        database=True,
        collection_label="Tabella",
        default_collection="embeddings",
        notes="Richiede l'estensione PostgreSQL `vector`.",
    ),
    DatabaseSpec(
        id="redis-vector",
        name="Redis Stack (vettori)",
        family=DatabaseFamily.VECTOR,
        description="Ricerca vettoriale e ibrida su Redis Stack/RediSearch.",
        accent="#DC382D",
        default_port=6379,
        scheme="redis",
        docker_host="redis",
        collection_label="Index",
        default_collection="documents_idx",
    ),
    DatabaseSpec(
        id="elasticsearch",
        name="Elasticsearch",
        family=DatabaseFamily.VECTOR,
        description="Search engine con kNN, dense vector e BM25.",
        accent="#FEC514",
        default_port=9200,
        scheme="http",
        docker_host="elasticsearch",
        health_path="/",
        auth=True,
        collection_label="Index",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="opensearch",
        name="OpenSearch",
        family=DatabaseFamily.VECTOR,
        description="Search engine open source con kNN e sicurezza integrata.",
        accent="#005EB8",
        default_port=9200,
        scheme="https",
        docker_host="opensearch",
        health_path=_HEALTH_OPENSEARCH,
        auth=True,
        collection_label="Index",
        default_collection="documents",
    ),
    # ------------------------------------------------------------ relational
    DatabaseSpec(
        id="postgresql",
        name="PostgreSQL",
        family=DatabaseFamily.RELATIONAL,
        description="Database relazionale SQL.",
        accent="#336791",
        default_port=5432,
        scheme="postgresql+psycopg",
        docker_host="postgres",
        auth=True,
        database=True,
        collection_label="Tabella",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="mysql",
        name="MySQL",
        family=DatabaseFamily.RELATIONAL,
        description="Database relazionale SQL.",
        accent="#00758F",
        default_port=3306,
        scheme="mysql+pymysql",
        docker_host="mysql",
        auth=True,
        database=True,
        collection_label="Tabella",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="mariadb",
        name="MariaDB",
        family=DatabaseFamily.RELATIONAL,
        description="Fork open source di MySQL.",
        accent="#C07639",
        default_port=3306,
        scheme="mysql+pymysql",
        docker_host="mariadb",
        auth=True,
        database=True,
        collection_label="Tabella",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="sqlite",
        name="SQLite",
        family=DatabaseFamily.RELATIONAL,
        description="Database SQL embedded su file, senza server.",
        accent="#7B8FA1",
        scheme="sqlite",
        embedded_path="./.ragstudio/ragstudio.sqlite3",
        collection_label="Tabella",
        default_collection="documents",
        supports_embedded=True,
        supports_remote=False,
    ),
    DatabaseSpec(
        id="duckdb",
        name="DuckDB",
        family=DatabaseFamily.RELATIONAL,
        description="Database analitico embedded per query su file.",
        accent="#FFF100",
        scheme="duckdb",
        embedded_path="./.ragstudio/ragstudio.duckdb",
        collection_label="Tabella",
        default_collection="documents",
        supports_embedded=True,
        supports_remote=False,
    ),
    DatabaseSpec(
        id="mssql",
        name="SQL Server",
        family=DatabaseFamily.RELATIONAL,
        description="Database relazionale Microsoft SQL Server.",
        accent="#CC2927",
        default_port=1433,
        scheme="mssql+pyodbc",
        docker_host="mssql",
        auth=True,
        database=True,
        collection_label="Tabella",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="oracle",
        name="Oracle",
        family=DatabaseFamily.RELATIONAL,
        description="Database relazionale Oracle.",
        accent="#F80000",
        default_port=1521,
        scheme="oracle+oracledb",
        docker_host="oracle",
        auth=True,
        collection_label="Tabella",
        default_collection="documents",
    ),
    # --------------------------------------------------------------- document
    DatabaseSpec(
        id="mongodb",
        name="MongoDB",
        family=DatabaseFamily.DOCUMENT,
        description="Database documentale con collezioni JSON.",
        accent="#47A248",
        default_port=27017,
        scheme="mongodb",
        docker_host="mongo",
        auth=True,
        database=True,
        collection_label="Collection",
        default_collection="documents",
    ),
    DatabaseSpec(
        id="couchdb",
        name="CouchDB",
        family=DatabaseFamily.DOCUMENT,
        description="Database documentale con API HTTP e sync.",
        accent="#E42528",
        default_port=5984,
        scheme="http",
        docker_host="couchdb",
        health_path="/",
        auth=True,
        database=True,
        collection_label="Design doc",
        default_collection="documents",
    ),
    # ------------------------------------------------------------------ cache
    DatabaseSpec(
        id="redis",
        name="Redis",
        family=DatabaseFamily.CACHE,
        description="Key-value store in memoria, cache e code.",
        accent="#DC382D",
        default_port=6379,
        scheme="redis",
        docker_host="redis",
        collection_label="Prefisso chiavi",
        default_collection="ragstudio:",
    ),
    DatabaseSpec(
        id="memcached",
        name="Memcached",
        family=DatabaseFamily.CACHE,
        description="Cache distribuita chiave-valore.",
        accent="#FF6B35",
        default_port=11211,
        scheme="memcached",
        docker_host="memcached",
    ),
    # ------------------------------------------------------------------ graph
    DatabaseSpec(
        id="neo4j",
        name="Neo4j",
        family=DatabaseFamily.GRAPH,
        description="Database a grafo con query Cypher.",
        accent="#018BFF",
        default_port=7687,
        scheme="bolt",
        docker_host="neo4j",
        auth=True,
        database=True,
        collection_label="Database attivo",
        default_collection="neo4j",
        notes="Porta HTTP di default per l'health check: 7474.",
    ),
    # ------------------------------------------------------------ time series
    DatabaseSpec(
        id="influxdb",
        name="InfluxDB",
        family=DatabaseFamily.TIME_SERIES,
        description="Database per serie temporali e metriche.",
        accent="#22ADF6",
        default_port=8086,
        scheme="http",
        docker_host="influxdb",
        health_path="/health",
        token=True,
        collection_label="Bucket",
        default_collection="ragstudio",
        extra_fields=(
            FieldSpec(key="organization", label="Organizzazione", default="ragstudio"),
        ),
    ),
    # ----------------------------------------------------------------- search
    DatabaseSpec(
        id="solr",
        name="Solr",
        family=DatabaseFamily.SEARCH,
        description="Piattaforma di ricerca full-text basata su Lucene.",
        accent="#D9411E",
        default_port=8983,
        scheme="http",
        docker_host="solr",
        health_path="/solr/admin/info/system",
        collection_label="Core / Collection",
        default_collection="documents",
    ),
)

SPECS: dict[str, DatabaseSpec] = {spec.id: spec for spec in CATALOG}


class DatabaseField(BaseModel):
    """Campo ancora richiesto all'utente (non derivabile dal catalogo)."""

    key: str
    label: str
    kind: FieldKind
    required: bool
    default: str | int | None = None
    options: list[str] = Field(default_factory=list)
    help: str = ""
    derived: bool = False
    visible_when: dict[str, Any] | None = None


class DatabaseCatalogEntry(BaseModel):
    id: str
    name: str
    family: DatabaseFamily
    description: str
    accent: str
    modes: list[ConnectionMode]
    default_port: int | None = None
    scheme: str = ""
    docker_host: str = "localhost"
    embedded_path: str | None = None
    health_path: str | None = None
    default_container: str | None = None
    collection_label: str | None = None
    default_collection: str | None = None
    notes: str = ""
    required_fields: list[DatabaseField] = Field(default_factory=list)

    def fields(self, mode: ConnectionMode, target: ConnectionTarget) -> list[DatabaseField]:
        return [
            DatabaseField(
                key=item.key,
                label=item.label,
                kind=item.kind,
                required=item.required,
                default=item.default,
                options=list(item.options),
                help=item.help,
                derived=item.derived,
                visible_when=item.visible_when,
            )
            for item in SPECS[self.id].fields_for(mode, target)
        ]


class ConnectionConfig(BaseModel):
    """Configurazione derivata e pronta per l'inizializzazione del client."""

    database: str
    name: str
    family: DatabaseFamily
    mode: ConnectionMode
    target: ConnectionTarget
    host: str | None = None
    port: int | None = None
    path: str | None = None
    scheme: str = ""
    url: str = ""
    private_url: str = Field(default="", exclude=True, description="URL con credenziali reali, mai esposto")
    container: str | None = None
    database_name: str | None = None
    collection: str | None = None
    options: dict[str, Any] = Field(default_factory=dict, description="Opzioni aggiuntive non segrete")
    secrets: dict[str, str] = Field(default_factory=dict, description="Chiavi/token/password")
    missing: list[str] = Field(default_factory=list, description="Campi obbligatori non valorizzati")

    def public_dict(self) -> dict[str, Any]:
        """Configurazione senza segreti, adatta a log/API/artifact."""

        payload = self.model_dump(mode="json")
        payload["secrets"] = {key: "***" for key in self.secrets}
        return payload


def get_spec(database_id: str) -> DatabaseSpec:
    spec = SPECS.get(database_id)
    if spec is None:
        raise ValueError(
            f"Database sconosciuto: {database_id!r}. Valori ammessi: {', '.join(SPECS)}"
        )
    return spec


def node_fields(spec: DatabaseSpec) -> list[FieldSpec]:
    """Parametri dichiarati nel nodo: tutti i campi, con regole di visibilità.

    La UI mostra solo quelli coerenti con modalità e target correnti; il
    backend riapplica la stessa regola quando deriva la configurazione.
    """

    modes = [mode for mode in ConnectionMode if spec.targets_for(mode)]
    default_mode = ConnectionMode.LOCAL if ConnectionMode.LOCAL in modes else modes[0]
    default_target = spec.targets_for(default_mode)[0]
    all_targets = tuple(target.value for target in ConnectionTarget if any(target in spec.targets_for(mode) for mode in modes))
    remote_targets = [target.value for target in (ConnectionTarget.LOCALHOST, ConnectionTarget.DOCKER, ConnectionTarget.IP)]

    fields = [
        FieldSpec(
            key="mode",
            label="Modalità",
            kind=FieldKind.SELECT,
            default=default_mode.value,
            options=tuple(mode.value for mode in modes),
            help="Locale: database embedded o servizio sulla macchina. Remoto: server raggiungibile in rete.",
        ),
        FieldSpec(
            key="target",
            label="Posizione",
            kind=FieldKind.SELECT,
            default=default_target.value,
            options=all_targets,
            help="Embedded/file, localhost, container Docker o indirizzo IP/hostname.",
        ),
        FieldSpec(
            key="host",
            label="IP o hostname",
            required=False,
            default=spec.docker_host,
            visible_when={"target": [ConnectionTarget.DOCKER.value, ConnectionTarget.IP.value]},
            help="Per Docker è derivato dal nome del servizio; per IP va indicato esplicitamente.",
        ),
        FieldSpec(
            key="port",
            label="Porta",
            kind=FieldKind.NUMBER,
            required=False,
            default=spec.default_port or "",
            derived=spec.default_port is not None,
            visible_when={"target": remote_targets},
            help="Derivata dal tipo di database; modificabile se il servizio usa un'altra porta.",
        ),
        FieldSpec(
            key="path",
            label="Percorso locale",
            kind=FieldKind.PATH,
            required=False,
            default=spec.embedded_path or "",
            derived=spec.embedded_path is not None,
            visible_when={"target": [ConnectionTarget.EMBEDDED.value]},
            help="File o cartella usata dal database embedded.",
        ),
    ]
    if spec.auth:
        fields.extend(
            [
                FieldSpec(
                    key="username",
                    label="Utente",
                    required=False,
                    visible_when={"target": remote_targets},
                ),
                FieldSpec(
                    key="password",
                    label="Password",
                    kind=FieldKind.PASSWORD,
                    required=False,
                    visible_when={"target": remote_targets},
                ),
            ]
        )
    if spec.token:
        fields.append(
            FieldSpec(
                key="apiKey",
                label="API key / token",
                kind=FieldKind.PASSWORD,
                required=False,
                visible_when={"target": remote_targets},
            )
        )
    if spec.database:
        fields.append(
            FieldSpec(
                key="database",
                label="Database",
                required=False,
                default=spec.default_collection or "",
                derived=spec.default_collection is not None,
                visible_when={"target": remote_targets},
            )
        )
    if spec.collection_label:
        fields.append(
            FieldSpec(
                key="collection",
                label=spec.collection_label,
                required=False,
                default=spec.default_collection or "",
                derived=spec.default_collection is not None,
                visible_when={"target": remote_targets},
            )
        )
    for item in spec.extra_fields:
        condition: dict[str, Any] = {}
        if item.targets:
            condition["target"] = [target.value for target in item.targets]
        fields.append(
            FieldSpec(
                key=item.key,
                label=item.label,
                kind=item.kind,
                required=False,
                default=item.default,
                options=item.options,
                help=item.help,
                visible_when=condition or None,
            )
        )
    if spec.family is DatabaseFamily.VECTOR:
        fields.append(
            FieldSpec(
                key="distance",
                label="Distanza",
                kind=FieldKind.SELECT,
                default="Cosine",
                options=("Cosine", "Dot", "Euclid"),
                help="Metrica usata per indicizzare e cercare i vettori.",
            )
        )
    else:
        fields.append(
            FieldSpec(
                key="query",
                label="Query (opzionale)",
                kind=FieldKind.TEXT,
                required=False,
                default="",
                help="Se impostata, la esegue sul database e restituisce Document[].",
            )
        )
    return fields


def catalog_entries() -> list[DatabaseCatalogEntry]:
    catalog_entries: list[DatabaseCatalogEntry] = [
        DatabaseCatalogEntry(
            id=spec.id,
            name=spec.name,
            family=spec.family,
            description=spec.description,
            accent=spec.accent,
            modes=[mode for mode in ConnectionMode if spec.targets_for(mode)],
            default_port=spec.default_port,
            scheme=spec.scheme,
            docker_host=spec.docker_host,
            embedded_path=spec.embedded_path,
            health_path=spec.health_path,
            default_container=spec.default_container,
            collection_label=spec.collection_label,
            default_collection=spec.default_collection,
            notes=spec.notes,
        )
        for spec in CATALOG
    ]
    for entry in catalog_entries:
        spec = SPECS[entry.id]
        mode = ConnectionMode.LOCAL if ConnectionMode.LOCAL in entry.modes else ConnectionMode.REMOTE
        entry.required_fields = entry.fields(mode, spec.targets_for(mode)[0])
    return catalog_entries


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def derive_connection(
    database_id: str,
    mode: ConnectionMode | str = ConnectionMode.REMOTE,
    target: ConnectionTarget | str | None = None,
    values: dict[str, Any] | None = None,
) -> ConnectionConfig:
    """Costruisce la configurazione derivando dal catalogo tutto ciò che può esserlo.

    I valori mancanti ma obbligatori finiscono in ``missing`` invece di
    generare un errore: la UI può mostrarli come campi da compilare.
    """

    spec = get_spec(database_id)
    mode = ConnectionMode(mode)
    values = dict(values or {})
    available = spec.targets_for(mode)
    if not available:
        raise ValueError(f"{spec.name} non supporta la modalità {mode.value}")
    target = ConnectionTarget(target) if target is not None else available[0]
    if target not in available:
        raise ValueError(
            f"{spec.name} non supporta il target {target.value} in modalità {mode.value}. "
            f"Valori ammessi: {', '.join(item.value for item in available)}"
        )

    host = ""
    if target is ConnectionTarget.LOCALHOST:
        host = "127.0.0.1"
    elif target is ConnectionTarget.DOCKER:
        host = _clean(values.get("host")) or spec.docker_host
    elif target is ConnectionTarget.IP:
        host = _clean(values.get("host"))

    port_value = values.get("port", spec.default_port)
    try:
        port = int(port_value) if port_value not in (None, "") else None
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Porta non valida: {port_value!r}") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"Porta fuori intervallo (1-65535): {port}")

    path = _clean(values.get("path")) or spec.embedded_path if target is ConnectionTarget.EMBEDDED else None
    database_name = _clean(values.get("database")) or (spec.default_collection if spec.database else None)
    collection = (
        _clean(values.get("collection"))
        or (spec.default_collection if spec.collection_label else None)
    )

    secrets: dict[str, str] = {}
    for key in ("username", "password", "apiKey", "token"):
        value = _clean(values.get(key))
        if value:
            secrets[key] = value

    options: dict[str, Any] = {}
    for item in spec.extra_fields:
        value = values.get(item.key, item.default)
        if value not in (None, ""):
            options[item.key] = value

    missing: list[str] = []
    if target is ConnectionTarget.IP and not host:
        missing.append("host")
    if target is not ConnectionTarget.EMBEDDED:
        if port is None:
            missing.append("port")
        if spec.auth and not secrets.get("username"):
            missing.append("username")
        if spec.auth and not secrets.get("password"):
            missing.append("password")
        if spec.token and not secrets.get("apiKey"):
            missing.append("apiKey")
        if spec.database and not database_name:
            missing.append("database")
    if target is ConnectionTarget.EMBEDDED and not path:
        missing.append("path")
    for item in spec.extra_fields:
        if item.required and item.key not in options:
            missing.append(item.key)

    url = _build_url(spec, target, host, port, path, database_name, secrets, options, redact=True)
    private_url = _build_url(spec, target, host, port, path, database_name, secrets, options, redact=False)
    return ConnectionConfig(
        database=spec.id,
        name=spec.name,
        family=spec.family,
        mode=mode,
        target=target,
        host=host or None,
        port=port,
        path=path,
        scheme=spec.scheme,
        url=url,
        private_url=private_url,
        container=spec.docker_host if target is ConnectionTarget.DOCKER else None,
        database_name=database_name,
        collection=collection,
        options=options,
        secrets=secrets,
        missing=missing,
    )


def _build_url(
    spec: DatabaseSpec,
    target: ConnectionTarget,
    host: str,
    port: int | None,
    path: str | None,
    database_name: str | None,
    secrets: dict[str, str],
    options: dict[str, Any],
    *,
    redact: bool = True,
) -> str:
    if target is ConnectionTarget.EMBEDDED:
        return f"{spec.scheme}:///{path.lstrip('/')}" if path else ""

    if spec.scheme.startswith("http"):
        base = f"{spec.scheme}://{host}"
        if port and port not in (80, 443):
            base += f":{port}"
        return base

    auth = ""
    if spec.auth and secrets.get("username"):
        user = secrets["username"]
        password = "***" if redact else secrets.get("password", "")
        auth = f"{user}:{password}@"
    elif secrets.get("apiKey"):
        api_key = "***" if redact else secrets["apiKey"]
        auth = f"default:{api_key}@"

    endpoint = host
    if port:
        endpoint = f"{host}:{port}" if ":" not in host else f"[{host}]:{port}"
    if spec.scheme == "sqlite":
        return f"sqlite:///{path.lstrip('/')}" if path else ""
    if spec.scheme == "bolt":
        return f"bolt://{endpoint}"
    if spec.scheme == "mongodb":
        return f"mongodb://{auth}{endpoint}/{database_name or ''}"
    name = ""
    if spec.scheme.startswith("postgresql") or spec.scheme.startswith("mysql"):
        name = f"/{database_name}" if database_name else ""
        if spec.scheme.startswith("mysql") and options.get("charset"):
            name += f"?charset={options['charset']}"
    elif spec.scheme.startswith("oracle"):
        name = f"/{database_name}" if database_name else ""
    elif spec.scheme == "redis":
        name = f"/{options.get('db', 0)}"
    return f"{spec.scheme}://{auth}{endpoint}{name}"


__all__ = [
    "CATALOG",
    "ConnectionConfig",
    "ConnectionMode",
    "ConnectionTarget",
    "DatabaseCatalogEntry",
    "DatabaseFamily",
    "DatabaseField",
    "DatabaseSpec",
    "FieldKind",
    "FieldSpec",
    "catalog_entries",
    "derive_connection",
    "get_spec",
    "node_fields",
]
