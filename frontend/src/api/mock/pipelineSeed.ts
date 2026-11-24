import type { NodeCategory, NodeDefinition, Pipeline, PortDefinition } from '@/types'
import { databaseNodeDefinitions } from './databases'

const port = (id: string, label: string, dataType: PortDefinition['dataType'], typeLabel: string, color: string): PortDefinition => ({
  id,
  label,
  dataType,
  typeLabel,
  color,
})

export const PORT_COLORS = {
  documents: '#39D6D0',
  chunks: '#A78BFA',
  embedding: '#7296FF',
  text: '#8AA0C0',
  json: '#F0B45C',
  query: '#5B7CFA',
  array: '#E48EF0',
  any: '#8C9AB2',
}

export const nodeDefinitions: NodeDefinition[] = [
  {
    id: 'document-source',
    name: 'Document source',
    category: 'Data Sources',
    kind: 'data-source',
    description: 'Loads documents from a directory, object store or connector.',
    summary: 'Ingest documents from a directory, S3 bucket or connector.',
    accent: '#39D6D0',
    tags: ['ingestion', 'files'],
    inputs: [],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'dataset', label: 'Dataset', type: 'select', defaultValue: 'ds_product_docs', options: ['ds_product_docs'], help: 'Dataset definiti nella pagina Datasets.' },
      { key: 'fileTypes', label: 'File types', type: 'select', defaultValue: 'all', options: ['all', 'pdf', 'text', 'txt', 'md', 'json', 'jsonl', 'csv', 'documents', 'other'], help: 'all | pdf | text | txt | md | json | jsonl | csv | documents | other' },
      { key: 'fileName', label: 'File name contains', type: 'text', defaultValue: '', help: 'Sottostringa o wildcard * nel nome/path, es. eni_*' },
      { key: 'limit', label: 'Document limit', type: 'number', defaultValue: 248 },
      { key: 'format', label: 'Parser', type: 'select', defaultValue: 'PDF → Markdown', options: ['PDF → Markdown', 'Plain text', 'HTML → Text', 'Auto-detect'] },
    ],
  },
  {
    id: 'merge-documents',
    name: 'Merge documents',
    category: 'Document Processing',
    kind: 'merge',
    description: 'Combine two filtered document branches (e.g. PDF and text) into one deduplicated stream.',
    summary: 'Combine PDF and text branches into one document stream.',
    accent: '#A78BFA',
    tags: ['merge', 'hybrid'],
    inputs: [
      port('in_documents_a', 'Documents A', 'documents', 'Document[]', '#39D6D0'),
      port('in_documents_b', 'Documents B', 'documents', 'Document[]', '#39D6D0'),
    ],
    outputs: [port('documents', 'Documents', 'documents', 'Document[]', '#39D6D0')],
    params: [],
  },
  {
    id: 'api-source',
    name: 'API source',
    category: 'Data Sources',
    kind: 'data-source',
    description: 'Pulls records from a REST API endpoint with pagination support.',
    accent: '#39D6D0',
    tags: ['ingestion', 'api'],
    inputs: [],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'endpoint', label: 'Endpoint', type: 'text', defaultValue: 'https://api.example.com/docs' },
      { key: 'auth', label: 'Auth header', type: 'text', defaultValue: 'Bearer ••••••••' },
      { key: 'pageSize', label: 'Page size', type: 'number', defaultValue: 100 },
    ],
  },
  {
    id: 'database-source',
    name: 'Database source',
    category: 'Data Sources',
    kind: 'data-source',
    description: 'Reads rows from PostgreSQL and maps them to documents.',
    accent: '#39D6D0',
    tags: ['ingestion', 'sql'],
    inputs: [],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'connection', label: 'Connection', type: 'text', defaultValue: 'postgres://workspace-db' },
      { key: 'table', label: 'Table', type: 'text', defaultValue: 'knowledge_articles' },
      { key: 'idColumn', label: 'ID column', type: 'text', defaultValue: 'id' },
    ],
  },
  {
    id: 'text-extraction',
    name: 'Text extraction',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Normalizes and cleans raw text before chunking.',
    accent: '#F0B45C',
    tags: ['processing'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'stripHeaders', label: 'Strip headers', type: 'boolean', defaultValue: true },
      { key: 'normalizeWhitespace', label: 'Normalize whitespace', type: 'boolean', defaultValue: true },
      { key: 'language', label: 'Language', type: 'select', defaultValue: 'Auto', options: ['Auto', 'English', 'Italian', 'German'] },
    ],
  },
  {
    id: 'semantic-chunking',
    name: 'Semantic Chunking',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Splits documents at meaningful boundaries using embedding similarity between sentences.',
    summary: 'Semantic-aware splitting that preserves document context.',
    documentation: 'Splits documents at meaningful boundaries using embedding similarity between sentences.',
    accent: '#A78BFA',
    tags: ['chunking', 'semantic'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [
      { key: 'chunkStrategy', label: 'Chunking strategy', type: 'select', defaultValue: 'fixed', options: ['fixed', 'recursive', 'sentence'], help: 'fixed | recursive | sentence produce visibly different chunks.' },
      { key: 'maxTokens', label: 'Maximum chunk size', type: 'number', defaultValue: 512, unit: 'tokens' },
      { key: 'overlap', label: 'Chunk overlap', type: 'number', defaultValue: 50, unit: 'tokens' },
    ],
  },
  {
    id: 'recursive-chunking',
    name: 'Recursive Chunking',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Recursively splits text on a configurable hierarchy of separators.',
    accent: '#F0B45C',
    tags: ['chunking'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [
      { key: 'chunkSize', label: 'Chunk size', type: 'number', defaultValue: 512, unit: 'tokens' },
      { key: 'overlap', label: 'Overlap', type: 'number', defaultValue: 64, unit: 'tokens' },
      { key: 'separators', label: 'Separators', type: 'text', defaultValue: '\\n\\n, \\n, . ' },
    ],
  },
  {
    id: 'ocr',
    name: 'OCR',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Extracts text from scanned pages and images using OCR.',
    accent: '#F0B45C',
    tags: ['ocr', 'vision'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'engine', label: 'Engine', type: 'select', defaultValue: 'Tesseract 5', options: ['Tesseract 5', 'PaddleOCR', 'Docling'] },
      { key: 'languages', label: 'Languages', type: 'text', defaultValue: 'eng' },
    ],
  },
  {
    id: 'table-extraction',
    name: 'Table extraction',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Detects and converts tables into structured markdown.',
    accent: '#F0B45C',
    tags: ['tables'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [{ key: 'algorithm', label: 'Algorithm', type: 'select', defaultValue: 'Camelot', options: ['Camelot', 'Tabula', 'Docling'] }],
  },
  {
    id: 'document-component-extraction',
    name: 'Document component extraction',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Extracts tables, images and charts from PDFs, describes visuals and merges them into document text.',
    summary: 'Turn PDF tables, images and charts into searchable text.',
    accent: '#E48EF0',
    tags: ['pdf', 'tables', 'images', 'vision'],
    inputs: [port('in_documents', 'Documents', 'documents', 'Document[]', '#39D6D0')],
    outputs: [
      port('out_documents', 'Documents', 'documents', 'Document[]', '#39D6D0'),
      port('out_components', 'Components', 'json', 'Component[]', '#F0B45C'),
    ],
    params: [
      { key: 'extractTables', label: 'Extract tables', type: 'boolean', defaultValue: true },
      { key: 'extractImages', label: 'Extract images', type: 'boolean', defaultValue: true },
      { key: 'extractFigures', label: 'Extract charts / figures', type: 'boolean', defaultValue: true },
      { key: 'descriptionMode', label: 'Visual description', type: 'select', defaultValue: 'reference', options: ['reference', 'openai', 'ollama', 'off'] },
      { key: 'visionModel', label: 'Vision model', type: 'text', defaultValue: '', help: 'Vuoto = modello predefinito del provider.' },
      { key: 'mergeIntoText', label: 'Merge into document text', type: 'boolean', defaultValue: true },
    ],
  },
  {
    id: 'visual-content-extractor',
    name: 'Visual content extractor',
    category: 'Document Processing',
    kind: 'processing',
    description: 'Describes contextualised PDF images/charts from their real artifact bytes with a vision model and emits text with provenance.',
    summary: 'Turn stored image bytes into cited text for retrieval.',
    accent: '#E48EF0',
    tags: ['pdf', 'images', 'vision', 'provenance'],
    inputs: [
      port('in_components', 'Components', 'json', 'Component[]', '#F0B45C'),
      port('in_query', 'Query', 'query', 'Query', '#39D6D0'),
    ],
    outputs: [
      port('out_documents', 'Visual text', 'documents', 'Document[]', '#39D6D0'),
      port('out_visual_text', 'Visual text (JSON)', 'json', 'VisualText[]', '#F0B45C'),
    ],
    params: [
      { key: 'provider', label: 'Vision provider', type: 'select', defaultValue: 'auto', options: ['auto', 'openai', 'ollama'] },
      { key: 'model', label: 'Vision model', type: 'text', defaultValue: '', help: 'Vuoto = modello predefinito del provider.' },
      { key: 'prompt', label: 'Prompt', type: 'textarea', defaultValue: 'Descrivi sinteticamente questa immagine o questo grafico in italiano. Indica il tipo di visualizzazione, le etichette principali e il messaggio informativo. Rispondi in 1-3 frasi, senza preambolo.', help: 'Segnaposto: {page}, {caption}, {summary}, {description}, {kind}, {query}.' },
      { key: 'requireContext', label: 'Solo immagini con contesto', type: 'boolean', defaultValue: true },
      { key: 'maxVisuals', label: 'Max immagini', type: 'number', defaultValue: 12 },
      { key: 'query', label: 'Query di contesto', type: 'text', defaultValue: '' },
    ],
  },
  {
    id: 'bge-embeddings',
    name: 'Mock embeddings (reference)',
    category: 'Embeddings',
    kind: 'embedding',
    description: 'Generates deterministic 128-dimensional hash vectors (mock reference, no real model).',
    accent: '#7296FF',
    tags: ['embedding', 'mock'],
    inputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    outputs: [port('embeddings', 'embeddings', 'embedding', 'List[Vector]', '#7296FF')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'Hash embeddings (reference)', options: ['Hash embeddings (reference)', 'Mock embedding', 'text-embedding-3-large (mock)'] },
      { key: 'dimensions', label: 'Dimensions', type: 'number', defaultValue: 128 },
      { key: 'batchSize', label: 'Batch size', type: 'number', defaultValue: 32 },
      { key: 'normalize', label: 'Normalize vectors', type: 'boolean', defaultValue: true },
    ],
  },
  {
    id: 'openai-embeddings',
    name: 'OpenAI Embeddings',
    category: 'Embeddings',
    kind: 'embedding',
    description: 'Embeds content with OpenAI text-embedding-3 models.',
    accent: '#7296FF',
    tags: ['embedding', 'openai'],
    inputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    outputs: [port('embeddings', 'embeddings', 'embedding', 'List[Vector]', '#7296FF')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'text-embedding-3-large (mock)', options: ['text-embedding-3-large (mock)', 'text-embedding-3-small (mock)'] },
      { key: 'dimensions', label: 'Dimensions', type: 'number', defaultValue: 3072 },
    ],
  },
  {
    id: 'ollama-embeddings',
    name: 'Ollama Embeddings',
    category: 'Embeddings',
    kind: 'embedding',
    description: 'Runs embeddings against a local Ollama runtime.',
    accent: '#7296FF',
    tags: ['embedding', 'ollama', 'local'],
    inputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    outputs: [port('embeddings', 'embeddings', 'embedding', 'List[Vector]', '#7296FF')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'nomic-embed-text (mock)', options: ['nomic-embed-text (mock)', 'mxbai-embed-large (mock)'] },
      { key: 'baseUrl', label: 'Base URL', type: 'text', defaultValue: 'http://localhost:11434' },
    ],
  },
  {
    id: 'qdrant-store',
    name: 'Qdrant store',
    category: 'Vector Databases',
    kind: 'vector-store',
    description: 'Upserts vectors and metadata into a Qdrant collection.',
    accent: '#7296FF',
    tags: ['vector', 'qdrant'],
    inputs: [port('embeddings', 'embeddings', 'embedding', 'List[Vector]', '#7296FF')],
    outputs: [port('store', 'store', 'any', 'QdrantCollection', '#8C9AB2')],
    params: [
      { key: 'collection', label: 'Collection', type: 'text', defaultValue: 'docs' },
      { key: 'distance', label: 'Distance metric', type: 'select', defaultValue: 'Cosine', options: ['Cosine', 'Euclidean', 'Dot'] },
      { key: 'vectorCount', label: 'Vectors', type: 'text', defaultValue: '24,816' },
      { key: 'recreate', label: 'Recreate collection', type: 'boolean', defaultValue: false },
    ],
  },
  {
    id: 'pgvector-store',
    name: 'pgvector store',
    category: 'Vector Databases',
    kind: 'vector-store',
    description: 'Stores embeddings in PostgreSQL with pgvector.',
    accent: '#7296FF',
    tags: ['vector', 'postgres'],
    inputs: [port('embeddings', 'embeddings', 'embedding', 'List[Vector]', '#7296FF')],
    outputs: [port('store', 'store', 'any', 'PgVectorTable', '#8C9AB2')],
    params: [
      { key: 'table', label: 'Table', type: 'text', defaultValue: 'document_chunks' },
      { key: 'index', label: 'Index', type: 'select', defaultValue: 'HNSW', options: ['HNSW', 'IVFFlat'] },
    ],
  },
  {
    id: 'query-input',
    name: 'Query input',
    category: 'Retrieval',
    kind: 'input',
    description: 'Accepts the user query at pipeline runtime.',
    accent: '#39D6D0',
    tags: ['user-input'],
    inputs: [],
    outputs: [port('query', 'query', 'query', 'String', '#39D6D0')],
    params: [
      { key: 'query', label: 'Query', type: 'text', defaultValue: 'How does hybrid retrieval work?', help: 'Testo usato quando il nodo non riceve una query dagli input.' },
      { key: 'variables', label: 'Variables', type: 'text', defaultValue: 'query: String' },
      { key: 'placeholder', label: 'Placeholder', type: 'text', defaultValue: 'Ask a question...' },
    ],
  },
  {
    id: 'bm25',
    name: 'BM25',
    category: 'Retrieval',
    kind: 'retrieval',
    description: 'Sparse keyword retrieval with BM25 scoring.',
    accent: '#F0B45C',
    tags: ['retrieval', 'sparse'],
    inputs: [port('query', 'query', 'query', 'String', '#39D6D0')],
    outputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [
      { key: 'topK', label: 'Top K', type: 'number', defaultValue: 20 },
      { key: 'k1', label: 'k1', type: 'number', defaultValue: 1.5 },
      { key: 'b', label: 'b', type: 'number', defaultValue: 0.75 },
    ],
  },
  {
    id: 'hybrid-retrieval',
    name: 'Hybrid Retrieval',
    category: 'Retrieval',
    kind: 'retrieval',
    description: 'Fuses dense vector search with sparse BM25 retrieval using reciprocal rank fusion.',
    accent: '#F0B45C',
    tags: ['retrieval', 'hybrid'],
    inputs: [
      port('query', 'query', 'query', 'String', '#39D6D0'),
      port('store', 'store', 'any', 'VectorStore', '#8C9AB2'),
    ],
    outputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C')],
    params: [
      { key: 'retrievalAlgorithm', label: 'Retrieval algorithm', type: 'select', defaultValue: 'hybrid', options: ['hybrid', 'dense', 'bm25', 'rrf'], help: 'hybrid | dense | bm25 | rrf change the ranking method.' },
      { key: 'alpha', label: 'Hybrid weight (alpha)', type: 'number', defaultValue: 0.7 },
      { key: 'topK', label: 'Top K', type: 'number', defaultValue: 20 },
    ],
  },
  {
    id: 'dense-retrieval',
    name: 'Dense retrieval',
    category: 'Retrieval',
    kind: 'retrieval',
    description: 'Semantic nearest-neighbour retrieval from a vector store.',
    accent: '#F0B45C',
    tags: ['retrieval', 'dense'],
    inputs: [port('query', 'query', 'query', 'String', '#39D6D0'), port('store', 'store', 'any', 'VectorStore', '#8C9AB2')],
    outputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C')],
    params: [
      { key: 'topK', label: 'Top K', type: 'number', defaultValue: 20 },
      { key: 'threshold', label: 'Min score', type: 'number', defaultValue: 0.65 },
    ],
  },
  {
    id: 'top-k',
    name: 'Top-K',
    category: 'Selection',
    kind: 'selection',
    description: 'Keeps the highest scoring candidates.',
    accent: '#A78BFA',
    tags: ['selection'],
    inputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C')],
    outputs: [port('selected', 'selected', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [{ key: 'k', label: 'K', type: 'number', defaultValue: 5 }],
  },
  {
    id: 'mmr',
    name: 'MMR',
    category: 'Selection',
    kind: 'selection',
    description: 'Maximal marginal relevance balances score and diversity.',
    accent: '#A78BFA',
    tags: ['selection', 'diversity'],
    inputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C')],
    outputs: [port('selected', 'selected', 'chunks', 'List[Chunk]', '#A78BFA')],
    params: [
      { key: 'k', label: 'Results', type: 'number', defaultValue: 5 },
      { key: 'lambda', label: 'Lambda', type: 'number', defaultValue: 0.7 },
    ],
  },
  {
    id: 'diversity-ranker',
    name: 'Diversity ranker',
    category: 'Selection',
    kind: 'selection',
    description: 'Balance relevance with semantic diversity.',
    accent: '#A78BFA',
    tags: ['selection', 'custom'],
    custom: true,
    version: 'v1.3.0',
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0'), port('query_embedding', 'query_embedding', 'embedding', 'ndarray', '#7296FF')],
    outputs: [port('ranked_documents', 'ranked_documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [
      { key: 'alpha', label: 'alpha · Relevance weight', type: 'number', defaultValue: 0.7 },
      { key: 'top_n', label: 'top_n · Results to return', type: 'number', defaultValue: 5 },
    ],
  },
  {
    id: 'bge-reranker',
    name: 'Mock reranker (reference)',
    category: 'Reranking',
    kind: 'reranking',
    description: 'Reference lexical reranking (mock only, no cross-encoder loaded).',
    accent: '#35D99B',
    tags: ['reranking', 'mock'],
    inputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C'), port('query', 'query', 'query', 'String', '#39D6D0')],
    outputs: [port('selected', 'selected', 'chunks', 'List[Chunk]', '#35D99B')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'Mock reranker', options: ['Mock reranker'] },
      { key: 'rerankStrategy', label: 'Reranking strategy', type: 'select', defaultValue: 'lexical', options: ['lexical', 'diversity', 'none'], help: 'lexical | diversity | none change the final ordering.' },
      { key: 'topN', label: 'Top N', type: 'number', defaultValue: 5 },
    ],
  },
  {
    id: 'cohere-reranker',
    name: 'Cohere Reranker',
    category: 'Reranking',
    kind: 'reranking',
    description: 'Managed cross-encoder reranking from Cohere.',
    accent: '#35D99B',
    tags: ['reranking', 'cohere'],
    inputs: [port('candidates', 'candidates', 'chunks', 'List[Chunk]', '#F0B45C')],
    outputs: [port('selected', 'selected', 'chunks', 'List[Chunk]', '#35D99B')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'rerank-v3.5 (mock)', options: ['rerank-v3.5 (mock)', 'rerank-english-v3.0 (mock)'] },
      { key: 'topN', label: 'Top N', type: 'number', defaultValue: 5 },
    ],
  },
  {
    id: 'prompt-assembly',
    name: 'Prompt assembly',
    category: 'LLM Generation',
    kind: 'generation',
    description: 'Builds the final grounded prompt with numbered sources.',
    accent: '#A78BFA',
    tags: ['prompt'],
    inputs: [port('chunks', 'chunks', 'chunks', 'List[Chunk]', '#A78BFA'), port('query', 'query', 'query', 'String', '#39D6D0')],
    outputs: [port('prompt', 'prompt', 'text', 'String', '#8AA0C0')],
    params: [
      { key: 'template', label: 'Template', type: 'select', defaultValue: 'Grounded QA', options: ['Grounded QA', 'Summarize', 'Cite sources'] },
      { key: 'maxContext', label: 'Max context', type: 'number', defaultValue: 4096, unit: 'tokens' },
    ],
  },
  {
    id: 'llm-generation',
    name: 'LLM Generation',
    category: 'LLM Generation',
    kind: 'generation',
    description: 'Generates a grounded answer from the assembled context.',
    accent: '#7296FF',
    tags: ['generation', 'llm'],
    inputs: [port('prompt', 'prompt', 'text', 'String', '#8AA0C0'), port('chunks', 'context', 'chunks', 'List[Chunk]', '#A78BFA')],
    outputs: [port('answer', 'answer', 'text', 'String', '#7296FF')],
    params: [
      { key: 'model', label: 'Model', type: 'select', defaultValue: 'Mock generation', options: ['Mock generation', 'Mock generation (concise)', 'Claude 3.5 Sonnet (mock)', 'Llama 3.1 8B (mock)'] },
      { key: 'generationStrategy', label: 'Generation strategy', type: 'select', defaultValue: 'extractive', options: ['extractive', 'first', 'concise'], help: 'extractive scores sentences; concise returns only the best sentence.' },
      { key: 'maxSentences', label: 'Max sentences', type: 'number', defaultValue: 3 },
      { key: 'temperature', label: 'Temperature', type: 'number', defaultValue: 0.2 },
    ],
  },
  {
    id: 'conditional-router',
    name: 'Conditional router',
    category: 'Control Flow',
    kind: 'control',
    description: 'Routes execution down one of several branches.',
    accent: '#8C9AB2',
    tags: ['control'],
    inputs: [port('input', 'input', 'any', 'Any', '#8C9AB2')],
    outputs: [port('true', 'true', 'any', 'Any', '#35D99B'), port('false', 'false', 'any', 'Any', '#F06A6A')],
    params: [{ key: 'expression', label: 'Condition', type: 'text', defaultValue: "confidence >= 0.8" }],
  },
  {
    id: 'merge',
    name: 'Merge',
    category: 'Control Flow',
    kind: 'control',
    description: 'Merges multiple document lists into one.',
    accent: '#8C9AB2',
    tags: ['control'],
    inputs: [port('a', 'a', 'documents', 'List[Document]', '#39D6D0'), port('b', 'b', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('merged', 'merged', 'documents', 'List[Document]', '#39D6D0')],
    params: [{ key: 'strategy', label: 'Strategy', type: 'select', defaultValue: 'Concat', options: ['Concat', 'Interleave', 'Dedupe'] }],
  },
  {
    id: 'faithfulness-scorer',
    name: 'Faithfulness scorer',
    category: 'Evaluation',
    kind: 'evaluation',
    description: 'Scores generated answers against retrieved context.',
    accent: '#A78BFA',
    tags: ['evaluation'],
    inputs: [port('answer', 'answer', 'text', 'String', '#7296FF'), port('chunks', 'context', 'chunks', 'List[Chunk]', '#A78BFA')],
    outputs: [port('score', 'score', 'json', 'Metric', '#F0B45C')],
    params: [{ key: 'judge', label: 'Judge model', type: 'select', defaultValue: 'Mock generation', options: ['Mock generation', 'Mock generation (concise)', 'Llama 3.1 8B (mock)'] }],
  },
  {
    id: 'vision-captioning',
    name: 'Vision captioning',
    category: 'Multimodal Processing',
    kind: 'multimodal',
    description: 'Generates descriptions for images and figures.',
    accent: '#E48EF0',
    tags: ['multimodal'],
    inputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    outputs: [port('documents', 'documents', 'documents', 'List[Document]', '#39D6D0')],
    params: [{ key: 'model', label: 'Model', type: 'select', defaultValue: 'Mock captioning', options: ['Mock captioning', 'LLaVA 1.6 (mock)'] }],
  },
  ...databaseNodeDefinitions(),
]

export const nodeDefById = Object.fromEntries(nodeDefinitions.map((n) => [n.id, n])) as Record<string, NodeDefinition>

export const nodeCategories: NodeCategory[] = [
  'Data Sources',
  'Document Processing',
  'Embeddings',
  'Vector Databases',
  'Databases',
  'Retrieval',
  'Selection',
  'Reranking',
  'LLM Generation',
  'Control Flow',
  'Evaluation',
  'Multimodal Processing',
]

export const PREFERRED_LIBRARY_NODES = [
  'document-source',
  'text-extraction',
  'ocr',
  'semantic-chunking',
  'recursive-chunking',
  'bge-embeddings',
  'openai-embeddings',
  'qdrant-store',
  'bm25',
  'hybrid-retrieval',
  'top-k',
  'mmr',
  'bge-reranker',
  'llm-generation',
  'conditional-router',
  'faithfulness-scorer',
  'vision-captioning',
]

function configFor(defId: string): Record<string, string | number | boolean> {
  const def = nodeDefById[defId]
  return Object.fromEntries(def.params.map((p) => [p.key, p.defaultValue]))
}

export function createNodeFromDefinition(defId: string, id: string, position: { x: number; y: number }) {
  const def = nodeDefById[defId]
  if (!def) throw new Error(`Unknown node definition: ${defId}`)
  return {
    id,
    definitionId: def.id,
    name: def.name,
    category: def.category,
    kind: def.kind,
    accent: def.accent,
    position,
    config: configFor(defId),
    inputs: def.inputs,
    outputs: def.outputs,
  }
}

export const seedPipeline: Pipeline = {
  id: 'pl_hybrid_rag',
  projectId: 'pr_knowledge',
  name: 'Hybrid RAG pipeline',
  description: 'Hybrid retrieval combines keyword matching with semantic search to improve relevance.',
  environment: 'Development',
  status: 'valid',
  version: 'v2.4',
  updatedAt: new Date(Date.now() - 4 * 60 * 1000).toISOString(),
  nodes: [
    {
      ...createNodeFromDefinition('document-source', 'n_document', { x: 40, y: 60 }),
      config: { dataset: 'ds_product_docs', limit: 248, format: 'PDF → Markdown' },
    },
    {
      ...createNodeFromDefinition('semantic-chunking', 'n_chunking', { x: 296, y: 60 }),
      config: { chunkStrategy: 'fixed', maxTokens: 512, overlap: 50 },
    },
    {
      ...createNodeFromDefinition('bge-embeddings', 'n_embeddings', { x: 552, y: 60 }),
      config: { model: 'Hash embeddings (reference)', dimensions: 128, batchSize: 32, normalize: true },
    },
    {
      ...createNodeFromDefinition('qdrant-store', 'n_qdrant', { x: 808, y: 60 }),
      config: { collection: 'docs', distance: 'Cosine', vectorCount: '24,816', recreate: false },
    },
    {
      ...createNodeFromDefinition('query-input', 'n_query', { x: 40, y: 388 }),
      config: { query: 'How does hybrid retrieval work?', variables: 'query: String' },
    },
    {
      ...createNodeFromDefinition('hybrid-retrieval', 'n_hybrid', { x: 296, y: 388 }),
      config: { retrievalAlgorithm: 'hybrid', alpha: 0.7, topK: 20 },
    },
    {
      ...createNodeFromDefinition('bge-reranker', 'n_reranker', { x: 552, y: 388 }),
      config: { model: 'Mock reranker', rerankStrategy: 'lexical', topN: 5 },
    },
    {
      ...createNodeFromDefinition('llm-generation', 'n_llm', { x: 808, y: 388 }),
      config: { model: 'Mock generation', generationStrategy: 'extractive', maxSentences: 3, temperature: 0.2 },
    },
  ],
  edges: [
    { id: 'e1', source: 'n_document', target: 'n_chunking', sourceHandle: 'documents', targetHandle: 'documents', dataType: 'documents' },
    { id: 'e2', source: 'n_chunking', target: 'n_embeddings', sourceHandle: 'chunks', targetHandle: 'chunks', dataType: 'chunks' },
    { id: 'e3', source: 'n_embeddings', target: 'n_qdrant', sourceHandle: 'embeddings', targetHandle: 'embeddings', dataType: 'embedding' },
    { id: 'e4', source: 'n_embeddings', target: 'n_reranker', sourceHandle: 'embeddings', targetHandle: 'candidates', dataType: 'embedding' },
    { id: 'e5', source: 'n_query', target: 'n_hybrid', sourceHandle: 'query', targetHandle: 'query', dataType: 'query' },
    { id: 'e6', source: 'n_qdrant', target: 'n_hybrid', sourceHandle: 'store', targetHandle: 'store', dataType: 'any' },
    { id: 'e7', source: 'n_hybrid', target: 'n_reranker', sourceHandle: 'candidates', targetHandle: 'candidates', dataType: 'chunks' },
    { id: 'e8', source: 'n_reranker', target: 'n_llm', sourceHandle: 'selected', targetHandle: 'chunks', dataType: 'chunks' },
    { id: 'e9', source: 'n_query', target: 'n_llm', sourceHandle: 'query', targetHandle: 'prompt', dataType: 'query' },
  ],
  lastRun: {
    status: 'completed',
    at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    latencyMs: 1240,
    tokens: 1842,
    cost: 0.0062,
    output:
      'Hybrid retrieval combines keyword matching with semantic search to improve relevance across both exact terminology and natural-language queries.',
    sources: 5,
  },
}

export const seedCustomNode = {
  id: 'cn_diversity',
  name: 'Diversity-aware ranker',
  slug: 'diversity-ranker',
  category: 'Selection',
  description: 'Replace Top-K with a custom relevance and diversity algorithm.',
  icon: 'sparkles',
  language: 'Python' as const,
  updatedAt: new Date(Date.now() - 60 * 1000).toISOString(),
  draftVersion: 'v1.3.0',
  basedOn: 'v1.2.0',
  files: [
    {
      id: 'f_py',
      name: 'Py ranker.py',
      language: 'python' as const,
      content: `from typing import List
import numpy as np
from rag_studio import CustomNode, Document

class DiversityRanker(CustomNode):
    """Balance relevance with semantic diversity."""

    name = "Diversity-aware ranker"
    category = "Selection"

    def execute(self, documents: List[Document],
                query_embedding: np.ndarray) -> List[Document]:
        alpha = self.params.get("alpha", 0.7)
        top_n = self.params.get("top_n", 5)
        selected, candidates = [], list(documents)

        while candidates and len(selected) < top_n:
            scores = [
                alpha * doc.relevance_score
                - (1 - alpha) * self.max_similarity(doc, selected)
                for doc in candidates
            ]
            best = candidates.pop(int(np.argmax(scores)))
            selected.append(best)

        return selected

    def max_similarity(self, doc: Document,
                       selected: List[Document]) -> float:
        if not selected:
            return 0.0
        return max(
            float(np.dot(doc.embedding, other.embedding))
            for other in selected
        )
`,
    },
    {
      id: 'f_yaml',
      name: 'config.yaml',
      language: 'yaml' as const,
      content: `name: Diversity-aware ranker
category: Selection
description: Balance relevance with semantic diversity.
version: 1.3.0

inputs:
  - name: documents
    type: List[Document]
  - name: query_embedding
    type: ndarray

outputs:
  - name: ranked_documents
    type: List[Document]

parameters:
  - name: alpha
    type: float
    default: 0.7
  - name: top_n
    type: int
    default: 5

dependencies:
  - numpy>=1.24.0
`,
    },
    {
      id: 'f_test',
      name: 'test_ranker.py',
      language: 'python' as const,
      content: `import pytest
from py_ranker import DiversityRanker

def test_returns_expected_count():
    result = DiversityRanker().execute(sample_docs, query_vec, top_n=5)
    assert len(result) == 5

def test_diversity_improves_coverage():
    result = DiversityRanker().execute(sample_docs, query_vec, alpha=0.7)
    assert diversity_score(result) > baseline_diversity

def test_handles_empty_documents():
    assert DiversityRanker().execute([], query_vec) == []
`,
    },
    {
      id: 'f_req',
      name: 'requirements.txt',
      language: 'text' as const,
      content: 'numpy>=1.24.0\n',
    },
  ],
  parameters: [
    { key: 'alpha', label: 'alpha · Relevance weight', type: 'float' as const, value: 0.7 },
    { key: 'top_n', label: 'top_n · Results to return', type: 'int' as const, value: 5 },
  ],
  inputDefinitions: [
    { id: 'documents', label: 'documents', dataType: 'documents' as const, typeLabel: 'List[Document]', color: '#39D6D0' },
    { id: 'query_embedding', label: 'query_embedding', dataType: 'embedding' as const, typeLabel: 'ndarray', color: '#A78BFA' },
  ],
  outputDefinitions: [
    { id: 'ranked_documents', label: 'ranked_documents', dataType: 'documents' as const, typeLabel: 'List[Document]', color: '#35D99B' },
  ],
  dependencies: [{ name: 'numpy', version: '>= 1.24.0', installed: true }],
  versions: [
    { id: 'v3', version: 'v1.3.0', label: 'Draft', date: 'just now', author: 'Alex Morgan', changes: 'Added similarity normalization and empty-list guard.', current: true },
    { id: 'v2', version: 'v1.2.0', label: 'Published', date: '2 hours ago', author: 'Alex Morgan', changes: 'Exposed top_n as a configurable parameter.' },
    { id: 'v1', version: 'v1.1.0', label: 'Published', date: 'Yesterday', author: 'Alex Morgan', changes: 'Initial diversity ranking implementation.' },
  ],
}
