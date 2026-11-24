/**
 * Mock del catalogo database: stessa forma dei modelli Pydantic del backend.
 * La derivazione è volutamente semplice ma usa le stesse regole di default,
 * così inspector e test funzionano anche con VITE_USE_MOCKS=true.
 */
import type {
  ConnectionMode,
  ConnectionTarget,
  DatabaseCatalogEntry,
  DatabaseCatalogResponse,
  DatabaseConnectionConfig,
  DatabaseConnectionRequest,
  DatabaseDeriveResponse,
  DatabaseFamily,
  DatabaseField,
  DatabaseFieldKind,
  DatabaseTestResponse,
  DatabaseValue,
  NodeDefinition,
  ParamDefinition,
} from '@/types'

interface ExtraField {
  key: string
  label: string
  default?: string | number
  help?: string
}

interface DatabaseSpec {
  id: string
  name: string
  family: DatabaseFamily
  description: string
  accent: string
  defaultPort?: number
  scheme: string
  dockerHost: string
  embeddedPath?: string
  healthPath?: string
  collectionLabel?: string
  defaultCollection?: string
  auth?: boolean
  token?: boolean
  database?: boolean
  embedded?: boolean
  remote?: boolean
  extra?: ExtraField[]
  notes?: string
}

type DatabaseSpecInput = Omit<DatabaseSpec, 'dockerHost' | 'remote'> & Partial<Pick<DatabaseSpec, 'dockerHost' | 'remote'>>

const spec = (value: DatabaseSpecInput): DatabaseSpec => ({
  ...value,
  dockerHost: value.dockerHost ?? 'localhost',
  remote: value.remote ?? true,
})

export const databaseSpecs: DatabaseSpec[] = [
  spec({ id: 'qdrant', name: 'Qdrant', family: 'vector', description: 'Vector database con ricerca ANN e filtri sui payload.', accent: '#F0B45C', defaultPort: 6333, scheme: 'http', dockerHost: 'qdrant', healthPath: '/healthz', collectionLabel: 'Collection', defaultCollection: 'documents' }),
  spec({ id: 'chroma', name: 'Chroma', family: 'vector', description: 'Vector store embedded o server con API HTTP.', accent: '#9D7BFF', defaultPort: 8000, scheme: 'http', dockerHost: 'chroma', embeddedPath: './.ragstudio/chroma', healthPath: '/api/v1/heartbeat', collectionLabel: 'Collection', defaultCollection: 'documents', embedded: true }),
  spec({ id: 'milvus', name: 'Milvus', family: 'vector', description: 'Vector database distribuito con indici HNSW/IVF.', accent: '#4EA8DE', defaultPort: 19530, scheme: 'http', dockerHost: 'milvus', collectionLabel: 'Collection', defaultCollection: 'documents' }),
  spec({ id: 'weaviate', name: 'Weaviate', family: 'vector', description: 'Vector store con schema, classi e moduli di vettorizzazione.', accent: '#FF8A65', defaultPort: 8080, scheme: 'http', dockerHost: 'weaviate', healthPath: '/v1/.well-known/ready', collectionLabel: 'Class', defaultCollection: 'Document' }),
  spec({ id: 'pinecone', name: 'Pinecone', family: 'vector', description: 'Vector database gestito: richiede API key e ambiente.', accent: '#22C55E', defaultPort: 443, scheme: 'https', token: true, collectionLabel: 'Index', defaultCollection: 'documents', extra: [{ key: 'environment', label: 'Environment', default: 'us-east-1', help: "Regione/cloud dell'account Pinecone." }] }),
  spec({ id: 'faiss', name: 'FAISS (locale)', family: 'vector', description: 'Indice vettoriale locale su file, senza server.', accent: '#60A5FA', scheme: 'faiss', embeddedPath: './.ragstudio/faiss.index', collectionLabel: 'Nome indice', defaultCollection: 'documents', embedded: true, remote: false }),
  spec({ id: 'pgvector', name: 'pgvector', family: 'vector', description: 'Estensione vettoriale di PostgreSQL.', accent: '#336791', defaultPort: 5432, scheme: 'postgresql+psycopg', dockerHost: 'postgres', auth: true, database: true, collectionLabel: 'Tabella', defaultCollection: 'embeddings', notes: 'Richiede l\'estensione PostgreSQL `vector`.' }),
  spec({ id: 'redis-vector', name: 'Redis Stack (vettori)', family: 'vector', description: 'Ricerca vettoriale e ibrida su Redis Stack/RediSearch.', accent: '#DC382D', defaultPort: 6379, scheme: 'redis', dockerHost: 'redis', collectionLabel: 'Index', defaultCollection: 'documents_idx' }),
  spec({ id: 'elasticsearch', name: 'Elasticsearch', family: 'vector', description: 'Search engine con kNN, dense vector e BM25.', accent: '#FEC514', defaultPort: 9200, scheme: 'http', dockerHost: 'elasticsearch', healthPath: '/', auth: true, collectionLabel: 'Index', defaultCollection: 'documents' }),
  spec({ id: 'opensearch', name: 'OpenSearch', family: 'vector', description: 'Search engine open source con kNN e sicurezza integrata.', accent: '#005EB8', defaultPort: 9200, scheme: 'https', dockerHost: 'opensearch', healthPath: '/_cluster/health', auth: true, collectionLabel: 'Index', defaultCollection: 'documents' }),
  spec({ id: 'postgresql', name: 'PostgreSQL', family: 'relational', description: 'Database relazionale SQL.', accent: '#336791', defaultPort: 5432, scheme: 'postgresql+psycopg', dockerHost: 'postgres', auth: true, database: true, collectionLabel: 'Tabella', defaultCollection: 'documents' }),
  spec({ id: 'mysql', name: 'MySQL', family: 'relational', description: 'Database relazionale SQL.', accent: '#00758F', defaultPort: 3306, scheme: 'mysql+pymysql', dockerHost: 'mysql', auth: true, database: true, collectionLabel: 'Tabella', defaultCollection: 'documents' }),
  spec({ id: 'mariadb', name: 'MariaDB', family: 'relational', description: 'Fork open source di MySQL.', accent: '#C07639', defaultPort: 3306, scheme: 'mysql+pymysql', dockerHost: 'mariadb', auth: true, database: true, collectionLabel: 'Tabella', defaultCollection: 'documents' }),
  spec({ id: 'sqlite', name: 'SQLite', family: 'relational', description: 'Database SQL embedded su file, senza server.', accent: '#7B8FA1', scheme: 'sqlite', embeddedPath: './.ragstudio/ragstudio.sqlite3', collectionLabel: 'Tabella', defaultCollection: 'documents', embedded: true, remote: false }),
  spec({ id: 'duckdb', name: 'DuckDB', family: 'relational', description: 'Database analitico embedded per query su file.', accent: '#FFF100', scheme: 'duckdb', embeddedPath: './.ragstudio/ragstudio.duckdb', collectionLabel: 'Tabella', defaultCollection: 'documents', embedded: true, remote: false }),
  spec({ id: 'mssql', name: 'SQL Server', family: 'relational', description: 'Database relazionale Microsoft SQL Server.', accent: '#CC2927', defaultPort: 1433, scheme: 'mssql+pyodbc', dockerHost: 'mssql', auth: true, database: true, collectionLabel: 'Tabella', defaultCollection: 'documents' }),
  spec({ id: 'oracle', name: 'Oracle', family: 'relational', description: 'Database relazionale Oracle.', accent: '#F80000', defaultPort: 1521, scheme: 'oracle+oracledb', dockerHost: 'oracle', auth: true, collectionLabel: 'Tabella', defaultCollection: 'documents' }),
  spec({ id: 'mongodb', name: 'MongoDB', family: 'document', description: 'Database documentale con collezioni JSON.', accent: '#47A248', defaultPort: 27017, scheme: 'mongodb', dockerHost: 'mongo', auth: true, database: true, collectionLabel: 'Collection', defaultCollection: 'documents' }),
  spec({ id: 'couchdb', name: 'CouchDB', family: 'document', description: 'Database documentale con API HTTP e sync.', accent: '#E42528', defaultPort: 5984, scheme: 'http', dockerHost: 'couchdb', healthPath: '/', auth: true, database: true, collectionLabel: 'Design doc', defaultCollection: 'documents' }),
  spec({ id: 'redis', name: 'Redis', family: 'cache', description: 'Key-value store in memoria, cache e code.', accent: '#DC382D', defaultPort: 6379, scheme: 'redis', dockerHost: 'redis', collectionLabel: 'Prefisso chiavi', defaultCollection: 'ragstudio:' }),
  spec({ id: 'memcached', name: 'Memcached', family: 'cache', description: 'Cache distribuita chiave-valore.', accent: '#FF6B35', defaultPort: 11211, scheme: 'memcached', dockerHost: 'memcached' }),
  spec({ id: 'neo4j', name: 'Neo4j', family: 'graph', description: 'Database a grafo con query Cypher.', accent: '#018BFF', defaultPort: 7687, scheme: 'bolt', dockerHost: 'neo4j', auth: true, database: true, collectionLabel: 'Database attivo', defaultCollection: 'neo4j', notes: 'Porta HTTP di default per l\'health check: 7474.' }),
  spec({ id: 'influxdb', name: 'InfluxDB', family: 'time-series', description: 'Database per serie temporali e metriche.', accent: '#22ADF6', defaultPort: 8086, scheme: 'http', dockerHost: 'influxdb', healthPath: '/health', token: true, collectionLabel: 'Bucket', defaultCollection: 'ragstudio', extra: [{ key: 'organization', label: 'Organizzazione', default: 'ragstudio' }] }),
  spec({ id: 'solr', name: 'Solr', family: 'search', description: 'Piattaforma di ricerca full-text basata su Lucene.', accent: '#D9411E', defaultPort: 8983, scheme: 'http', dockerHost: 'solr', healthPath: '/solr/admin/info/system', collectionLabel: 'Core / Collection', defaultCollection: 'documents' }),
]

export function getDatabaseSpec(databaseId: string): DatabaseSpec {
  const found = databaseSpecs.find((item) => item.id === databaseId)
  if (!found) throw new Error(`Database sconosciuto: ${databaseId}`)
  return found
}

function modesFor(item: DatabaseSpec): ConnectionMode[] {
  return [...(item.embedded || item.remote ? ['local' as const] : []), ...(item.remote ? ['remote' as const] : [])]
}

function targetsFor(item: DatabaseSpec, mode: ConnectionMode): ConnectionTarget[] {
  if (mode === 'local') {
    return [
      ...(item.embedded ? ['embedded' as const] : []),
      ...(item.remote ? ['localhost' as const, 'docker' as const] : []),
    ]
  }
  return item.remote ? ['docker', 'ip'] : []
}

const remoteTargets = ['localhost', 'docker', 'ip']

interface InternalField {
  key: string
  label: string
  kind: DatabaseFieldKind
  default: string | number | null
  options?: string[]
  help?: string
  derived?: boolean
  visibleWhen?: Record<string, string[]>
  secret?: boolean
  nodeOnly?: boolean
}

function fieldsFor(item: DatabaseSpec, mode: ConnectionMode, target: ConnectionTarget, node: boolean): InternalField[] {
  const remote = target !== 'embedded'
  const remoteVisibility = node ? { target: remoteTargets } : undefined
  const fields: InternalField[] = []
  if (node) {
    fields.push(
      { key: 'mode', label: 'Modalità', kind: 'select', default: modesFor(item)[0], options: modesFor(item), help: 'Locale: embedded o servizio locale. Remoto: server raggiungibile in rete.', nodeOnly: true },
      { key: 'target', label: 'Posizione', kind: 'select', default: targetsFor(item, mode)[0], options: [...new Set(modesFor(item).flatMap((value) => targetsFor(item, value)))], help: 'Embedded/file, localhost, container Docker o indirizzo IP/hostname.', nodeOnly: true },
    )
  }
  if (target === 'embedded') {
    fields.push({
      key: 'path',
      label: 'Percorso locale',
      kind: 'path',
      default: item.embeddedPath ?? '',
      derived: Boolean(item.embeddedPath),
      help: 'File o cartella usata dal database embedded.',
      ...(node ? { visibleWhen: { target: ['embedded'] } } : {}),
    })
  }
  if (node && remote) {
    fields.push({
      key: 'host',
      label: 'IP o hostname',
      kind: 'text',
      default: item.dockerHost,
      help: 'Per Docker è derivato dal nome del servizio; per IP va indicato esplicitamente.',
      visibleWhen: { target: ['docker', 'ip'] },
      nodeOnly: true,
    })
  } else if (target === 'ip') {
    fields.push({ key: 'host', label: 'IP o hostname', kind: 'text', default: '', help: 'Indirizzo del server database raggiungibile dalla rete.' })
  }
  if (item.defaultPort === undefined && remote) {
    fields.push({ key: 'port', label: 'Porta', kind: 'number', default: '' })
  }
  if (node && remote) {
    fields.push({
      key: 'port',
      label: 'Porta',
      kind: 'number',
      default: item.defaultPort ?? '',
      derived: Boolean(item.defaultPort),
      visibleWhen: { target: remoteTargets },
      help: 'Derivata dal tipo di database; modificabile se il servizio usa un\'altra porta.',
      nodeOnly: true,
    })
  }
  if (item.auth && remote) {
    fields.push({ key: 'username', label: 'Utente', kind: 'text', default: '', ...(remoteVisibility ? { visibleWhen: remoteVisibility } : {}) })
    fields.push({ key: 'password', label: 'Password', kind: 'password', default: '', secret: true, ...(remoteVisibility ? { visibleWhen: remoteVisibility } : {}) })
  }
  if (item.token && remote) {
    fields.push({ key: 'apiKey', label: 'API key / token', kind: 'password', default: '', secret: true, ...(remoteVisibility ? { visibleWhen: remoteVisibility } : {}) })
  }
  if (item.database && remote) {
    fields.push({ key: 'database', label: 'Database', kind: 'text', default: item.defaultCollection ?? '', derived: Boolean(item.defaultCollection), ...(remoteVisibility ? { visibleWhen: remoteVisibility } : {}) })
  }
  if (item.collectionLabel && remote) {
    fields.push({ key: 'collection', label: item.collectionLabel, kind: 'text', default: item.defaultCollection ?? '', derived: Boolean(item.defaultCollection), ...(remoteVisibility ? { visibleWhen: remoteVisibility } : {}) })
  }
  for (const extra of item.extra ?? []) {
    fields.push({ key: extra.key, label: extra.label, kind: 'text', default: extra.default ?? '', help: extra.help })
  }
  if (node) {
    fields.push(
      item.family === 'vector'
        ? { key: 'distance', label: 'Distanza', kind: 'select', default: 'Cosine', options: ['Cosine', 'Dot', 'Euclid'], help: 'Metrica usata per indicizzare e cercare i vettori.', nodeOnly: true }
        : { key: 'query', label: 'Query (opzionale)', kind: 'text', default: '', help: 'Se impostata, la esegue sul database e restituisce Document[].', nodeOnly: true },
    )
  }
  return fields
}

function catalogField(field: InternalField): DatabaseField {
  return {
    key: field.key,
    label: field.label,
    kind: field.kind,
    required: true,
    default: field.default,
    options: field.options ?? [],
    help: field.help ?? '',
    derived: Boolean(field.derived),
    ...(field.visibleWhen ? { visible_when: field.visibleWhen } : {}),
  }
}

export function databaseCatalog(): DatabaseCatalogResponse {
  const databases: DatabaseCatalogEntry[] = databaseSpecs.map((item) => {
    const mode = modesFor(item)[0]!
    return {
      id: item.id,
      name: item.name,
      family: item.family,
      description: item.description,
      accent: item.accent,
      modes: modesFor(item),
      default_port: item.defaultPort ?? null,
      scheme: item.scheme,
      docker_host: item.dockerHost,
      embedded_path: item.embeddedPath ?? null,
      health_path: item.healthPath ?? null,
      default_container: null,
      collection_label: item.collectionLabel ?? null,
      default_collection: item.defaultCollection ?? null,
      notes: item.notes ?? '',
      required_fields: fieldsFor(item, mode, targetsFor(item, mode)[0]!, false).map(catalogField),
    }
  })
  return { databases, total: databases.length }
}

function asText(value: DatabaseValue): string {
  return value === undefined || value === null ? '' : String(value).trim()
}

function buildUrl(item: DatabaseSpec, target: ConnectionTarget, host: string, port: number | null, path: string | null, databaseName: string | null, secrets: Record<string, string>): string {
  if (target === 'embedded') return path ? `${item.scheme}:///${path.replace(/^\//, '')}` : ''
  if (item.scheme.startsWith('http')) return `${item.scheme}://${host}${port && port !== 80 && port !== 443 ? `:${port}` : ''}`
  let auth = ''
  if (item.auth && secrets.username) auth = `${secrets.username}:${secrets.password ? '***' : ''}@`
  else if (secrets.apiKey) auth = `default:***@`
  const endpoint = port ? `${host}:${port}` : host
  if (item.scheme === 'bolt') return `bolt://${endpoint}`
  if (item.scheme === 'mongodb') return `mongodb://${auth}${endpoint}/${databaseName ?? ''}`
  const name = item.scheme.startsWith('postgresql') || item.scheme.startsWith('mysql') || item.scheme.startsWith('oracle')
    ? `/${databaseName ?? ''}`
    : ''
  return `${item.scheme}://${auth}${endpoint}${name}`
}

export function deriveDatabase(request: DatabaseConnectionRequest): DatabaseDeriveResponse {
  const item = getDatabaseSpec(request.database ?? '')
  const modes = modesFor(item)
  const mode = request.mode ?? modes[0]!
  if (!modes.includes(mode)) throw new Error(`${item.name} non supporta la modalità ${mode}`)
  const targets = targetsFor(item, mode)
  const target = request.target ?? targets[0]!
  if (!targets.includes(target)) throw new Error(`${item.name} non supporta il target ${target} in modalità ${mode}`)

  const values = request.values ?? {}
  const host = target === 'localhost' ? '127.0.0.1' : target === 'docker' ? asText(values.host) || item.dockerHost : target === 'ip' ? asText(values.host) : ''
  const portValue = values.port ?? item.defaultPort
  const port = portValue === undefined || portValue === null || portValue === '' ? null : Number(portValue)
  if (port !== null && (!Number.isInteger(port) || port < 1 || port > 65535)) throw new Error(`Porta non valida: ${String(portValue)}`)
  const path = target === 'embedded' ? asText(values.path) || item.embeddedPath || null : null
  const databaseName = asText(values.database) || (item.database ? item.defaultCollection ?? null : null)
  const collection = asText(values.collection) || item.defaultCollection || null

  const secrets: Record<string, string> = {}
  for (const key of ['username', 'password', 'apiKey', 'token']) {
    const value = asText(values[key])
    if (value) secrets[key] = value
  }
  const options: Record<string, unknown> = {}
  for (const extra of item.extra ?? []) {
    const value = values[extra.key] ?? extra.default
    if (value !== undefined && value !== null && value !== '') options[extra.key] = value
  }
  const missing: string[] = []
  if (target === 'ip' && !host) missing.push('host')
  if (target !== 'embedded') {
    if (port === null) missing.push('port')
    if (item.auth && !secrets.username) missing.push('username')
    if (item.auth && !secrets.password) missing.push('password')
    if (item.token && !secrets.apiKey) missing.push('apiKey')
    if (item.database && !databaseName) missing.push('database')
  }
  if (target === 'embedded' && !path) missing.push('path')
  for (const extra of item.extra ?? []) {
    if (extra.default === undefined && !options[extra.key]) missing.push(extra.key)
  }
  const config: DatabaseConnectionConfig = {
    database: item.id,
    name: item.name,
    family: item.family,
    mode,
    target,
    host: host || null,
    port,
    path,
    scheme: item.scheme,
    url: buildUrl(item, target, host, port, path, databaseName, secrets),
    container: target === 'docker' ? item.dockerHost : null,
    database_name: databaseName,
    collection,
    options,
    secrets: Object.fromEntries(Object.keys(secrets).map((key) => [key, '***'])),
    missing,
  }
  return { ...config, fields: fieldsFor(item, mode, target, false).map(catalogField) }
}

export function testDatabase(request: DatabaseConnectionRequest): DatabaseTestResponse {
  return {
    ok: false,
    detail: 'Mock adapter: il test reale di connessione richiede VITE_USE_MOCKS=false e il backend.',
    latencyMs: 0,
    config: deriveDatabase(request),
  }
}

function toParam(field: InternalField, item: DatabaseSpec): ParamDefinition {
  const type = field.kind === 'number' ? 'number' : field.kind === 'select' ? 'select' : 'text'
  return {
    key: field.key,
    label: field.label,
    type,
    defaultValue: field.default ?? '',
    ...(field.options ? { options: field.options } : {}),
    help: field.help ?? '',
    ...(field.secret ? { secret: true } : {}),
    ...(field.derived ? { derived: true } : {}),
    ...(field.visibleWhen ? { visibleWhen: field.visibleWhen } : {}),
    ...(field.nodeOnly && field.key === 'target' ? { optionsByMode: Object.fromEntries(modesFor(item).map((mode) => [mode, targetsFor(item, mode)])) } : {}),
  }
}

export function databaseNodeDefinitions(): NodeDefinition[] {
  return databaseSpecs.map((item) => {
    const mode = modesFor(item)[0]!
    const vector = item.family === 'vector'
    return {
      id: `db-${item.id}`,
      name: `${item.name} connection`,
      category: vector ? 'Vector Databases' : 'Databases',
      kind: vector ? 'vector-store' : 'source',
      description: item.description,
      summary: `Collega ${item.name} (locale o remoto) e restituisce una connessione utilizzabile nella pipeline.`,
      documentation: `Porta, protocollo, host Docker e nomi predefiniti sono derivati dal tipo di database.${item.notes ? ` ${item.notes}` : ''}`,
      accent: item.accent,
      tags: ['database', item.family, item.id, 'connection'],
      version: '1.0.0',
      inputs: vector ? [{ id: 'in_embedding', label: 'Embeddings', dataType: 'embedding', typeLabel: 'Embedding[]', color: '#7296FF' }] : [],
      outputs: vector
        ? [
            { id: 'out_index', label: 'Index', dataType: 'json', typeLabel: 'IndexRef', color: '#F0B45C' },
            { id: 'out_connection', label: 'Connessione', dataType: 'json', typeLabel: 'ConnectionRef', color: '#35D99B' },
          ]
        : [
            { id: 'out_documents', label: 'Documenti', dataType: 'documents', typeLabel: 'Document[]', color: '#39D6D0' },
            { id: 'out_connection', label: 'Connessione', dataType: 'json', typeLabel: 'ConnectionRef', color: '#35D99B' },
          ],
      params: fieldsFor(item, mode, targetsFor(item, mode)[0]!, true).map((field) => toParam(field, item)),
    }
  })
}
