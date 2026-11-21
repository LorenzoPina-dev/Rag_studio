/**
 * Static dataset for the techniques catalog in mock mode.
 * Mirrors the Pydantic payloads served by /api/v1/techniques.
 */
import type { CategorySummary, PhaseSummary, Technique, TechniqueStatus } from '@/types/techniques'
import { TECHNIQUE_STATUSES } from '@/types/techniques'

type Seed = [
  id: string,
  name: string,
  category: string,
  phase: string,
  status: TechniqueStatus,
  description: string,
  implementation: string,
  tags: string[],
  parameters?: Record<string, unknown>,
]

const seeds: Seed[] = [
  // ── Preprocessing ──────────────────────────────────────────────────────────
  ['fixed-chunking', 'Fixed-size chunking', 'Preprocessing', 'Ingestion', 'reference', 'Split documents into uniformly sized chunks with a fixed overlap. Simple and predictable baseline.', 'Text splitter over characters or tokens; deterministic offsets kept for citations.', ['chunking', 'baseline'], { chunk_size: 512, overlap: 64, unit: 'tokens' }],
  ['recursive-chunking', 'Recursive character chunking', 'Preprocessing', 'Ingestion', 'reference', 'Recursively split on separators (paragraphs, sentences, words) until chunks fit the target size.', 'Hierarchical separator list with length-based fallback and overlap.', ['chunking', 'text'], { separators: ['\n\n', '\n', '. ', ' '], chunk_size: 512 }],
  ['semantic-chunking', 'Semantic chunking', 'Preprocessing', 'Ingestion', 'reference', 'Group adjacent sentences by embedding similarity so each chunk covers one coherent idea.', 'Sentence embeddings + consecutive-similarity thresholding.', ['chunking', 'embeddings'], { threshold: 0.72, max_chunk_size: 800 }],
  ['token-aware-chunking', 'Token-aware chunking', 'Preprocessing', 'Ingestion', 'reference', 'Chunk using the target tokenizer so chunks never exceed the model context budget.', 'Tokenizer-driven splitter with exact token counts.', ['chunking', 'tokens'], { chunk_size: 512, tokenizer: 'cl100k_base' }],
  ['layout-parsing', 'Document layout parsing', 'Preprocessing', 'Ingestion', 'provider', 'Detect headings, columns, lists and tables to preserve document structure during ingestion.', 'Managed document-layout API returning structured blocks and reading order.', ['parsing', 'layout'], { model: 'layout-v2', keep_tables: true }],
  ['ocr-extraction', 'OCR and table extraction', 'Preprocessing', 'Ingestion', 'provider', 'Extract text from scanned pages and reconstruct tables as structured rows.', 'OCR service with table-structure recognition and confidence scores.', ['ocr', 'tables'], { language: 'auto', min_confidence: 0.85 }],
  ['language-normalization', 'Language detection and normalization', 'Preprocessing', 'Ingestion', 'reference', 'Detect language, normalize unicode and strip boilerplate before downstream processing.', 'Rule-based normalization plus lightweight language classifier.', ['normalization'], { unicode_form: 'NFC', strip_boilerplate: true }],
  ['content-deduplication', 'Content deduplication', 'Preprocessing', 'Ingestion', 'reference', 'Remove repeated or near-duplicate documents and chunks to avoid skew in retrieval.', 'MinHash/LSH similarity with configurable Jaccard threshold.', ['dedup', 'lsh'], { threshold: 0.9, window: 5 }],
  ['metadata-extraction', 'Metadata extraction', 'Preprocessing', 'Ingestion', 'reference', 'Attach titles, section paths, dates and source URLs to chunks for filtering and citations.', 'Regex and DOM-based field extraction merged with file metadata.', ['metadata'], { fields: ['title', 'section', 'source', 'date'] }],
  // ── Enrichment ─────────────────────────────────────────────────────────────
  ['hyde', 'Hypothetical document embeddings (HyDE)', 'Enrichment', 'Retrieval', 'design', 'Generate a hypothetical answer first and retrieve using its embedding to bridge query/document mismatch.', 'LLM-generated pseudo-document embedded with the same retrieval encoder.', ['query', 'embeddings'], { generated_docs: 1, temperature: 0.2 }],
  ['contextual-headers', 'Contextual chunk headers', 'Enrichment', 'Ingestion', 'design', 'Prepend the section hierarchy to each chunk before embedding to retain document context.', 'Build header paths from layout blocks and prefix chunk text.', ['chunking', 'metadata'], { max_depth: 3, separator: ' > ' }],
  ['entity-extraction', 'Named entity enrichment', 'Enrichment', 'Ingestion', 'provider', 'Tag people, organizations and domain entities to improve filtering and explainability.', 'NER API with dictionary-based domain overrides.', ['entities', 'metadata'], { model: 'ner-enterprise', confidence: 0.8 }],
  ['knowledge-graph-enrichment', 'Knowledge graph enrichment', 'Enrichment', 'Ingestion', 'design', 'Link entities and relations into a graph to support multi-hop queries.', 'Triplet extraction plus graph store with entity resolution.', ['graph', 'multi-hop'], { max_triplets_per_chunk: 8 }],
  ['query-expansion', 'Query expansion', 'Enrichment', 'Retrieval', 'reference', 'Add synonyms and domain variants to the query to improve recall on terse questions.', 'Synonym dictionary and pseudo-relevance feedback from top hits.', ['query', 'recall'], { synonyms: 4, feedback_docs: 3 }],
  ['query-rewriting', 'Query rewriting', 'Enrichment', 'Retrieval', 'design', 'Rewrite conversational or ambiguous questions into standalone search queries.', 'LLM rewrite prompted with recent conversation turns.', ['query', 'llm'], { history_turns: 3, temperature: 0 }],
  ['multi-query-retrieval', 'Multi-query retrieval', 'Enrichment', 'Retrieval', 'design', 'Generate several query perspectives and merge their result sets before ranking.', 'LLM query variants fanned out over the same retriever.', ['query', 'fusion'], { variants: 4 }],
  ['synthetic-qa', 'Synthetic QA pairs', 'Enrichment', 'Ingestion', 'design', 'Generate question/answer pairs per chunk to train or evaluate retrieval on a new corpus.', 'LLM generation with grounded-answer validation.', ['synthetic', 'evaluation'], { pairs_per_chunk: 2 }],
  ['document-summarization', 'Document summarization', 'Enrichment', 'Ingestion', 'provider', 'Create concise abstracts used as retrieval proxies for long documents.', 'Managed summarization API with map-reduce over sections.', ['summary'], { max_words: 120 }],
  // ── Indexing & Storage ─────────────────────────────────────────────────────
  ['dense-index', 'Dense vector indexing', 'Indexing & Storage', 'Indexing', 'reference', 'Embed chunks and store vectors for semantic nearest-neighbour search.', 'Batch embedding + vector collection with cosine similarity.', ['embeddings', 'vector'], { dimensions: 1536, metric: 'cosine' }],
  ['sparse-bm25', 'Sparse BM25 indexing', 'Indexing & Storage', 'Indexing', 'reference', 'Build an inverted index with BM25 scoring for exact keyword matching.', 'Tokenized inverted index with IDF statistics.', ['lexical', 'bm25'], { k1: 1.5, b: 0.75 }],
  ['hybrid-index', 'Hybrid index', 'Indexing & Storage', 'Indexing', 'reference', 'Maintain dense and sparse indexes side by side for combined retrieval.', 'Dual indexing pipeline with shared chunk identifiers.', ['hybrid'], { dense_weight: 0.7 }],
  ['hnsw', 'HNSW approximate search', 'Indexing & Storage', 'Indexing', 'integration', 'Use hierarchical navigable small-world graphs for fast approximate vector search at scale.', 'Vector store HNSW index with tuned build/search parameters.', ['ann', 'vector'], { m: 16, ef_construction: 128, ef_search: 64 }],
  ['ivf-pq', 'IVF-PQ compression', 'Indexing & Storage', 'Indexing', 'integration', 'Compress vectors with product quantization to reduce memory for very large corpora.', 'Vector store IVF index with PQ codebooks.', ['ann', 'compression'], { nlist: 256, m: 16 }],
  ['multi-vector-index', 'Multi-vector indexing (ColBERT)', 'Indexing & Storage', 'Indexing', 'design', 'Store one vector per token and use late interaction for finer-grained matching.', 'ColBERT-style token embeddings with MaxSim scoring.', ['late-interaction'], { max_tokens: 256 }],
  ['parent-child-index', 'Parent-child chunk indexing', 'Indexing & Storage', 'Indexing', 'design', 'Retrieve small child chunks but return their larger parent for complete context.', 'Two-level chunk store with parent references.', ['chunking', 'context'], { child_size: 256, parent_size: 1024 }],
  ['metadata-filter-index', 'Metadata filter indexing', 'Indexing & Storage', 'Indexing', 'integration', 'Index structured fields alongside vectors for pre-filtered search.', 'Vector store payload indexes on scalar and tag fields.', ['filtering', 'vector'], { fields: ['tenant_id', 'locale', 'year'] }],
  ['incremental-reindex', 'Incremental re-indexing', 'Indexing & Storage', 'Indexing', 'integration', 'Update only changed chunks using content hashes and deletion tombstones.', 'Change-detection job with idempotent upserts.', ['operations'], { batch_size: 256, checksum: 'sha256' }],
  // ── Fusion ─────────────────────────────────────────────────────────────────
  ['rrf', 'Reciprocal rank fusion', 'Fusion', 'Retrieval', 'reference', 'Combine ranked lists using reciprocal ranks, avoiding score-scale normalization.', 'Score = Σ 1/(k + rank) across retrievers.', ['fusion', 'ranking'], { k: 60 }],
  ['weighted-fusion', 'Weighted score fusion', 'Fusion', 'Retrieval', 'reference', 'Blend normalized scores from multiple retrievers with configurable weights.', 'Min-max normalization followed by weighted sum.', ['fusion', 'ranking'], { alpha: 0.7 }],
  ['relative-fusion', 'Relative score fusion', 'Fusion', 'Retrieval', 'reference', 'Normalize each list by its maximum score before summing to reduce scale bias.', 'Score scaling against observed hit distribution.', ['fusion'], { top_n: 20 }],
  ['distribution-fusion', 'Distribution-based score fusion', 'Fusion', 'Retrieval', 'design', 'Normalize scores using each retriever’s mean and standard deviation.', 'Z-score normalization across candidate lists.', ['fusion', 'statistics'], { z_clip: 3 }],
  ['multi-retriever-fusion', 'Multi-retriever fusion', 'Fusion', 'Retrieval', 'design', 'Run lexical, semantic and graph retrievers in parallel and fuse their candidates.', 'Parallel retriever fan-out with rank fusion.', ['fusion', 'recall'], { retrievers: ['bm25', 'dense', 'graph'] }],
  ['cross-encoder-rerank', 'Cross-encoder reranking', 'Fusion', 'Retrieval', 'provider', 'Score query-document pairs jointly for higher precision than bi-encoder similarity.', 'Local cross-encoder scoring top_n candidates.', ['reranking', 'precision'], { top_n: 20, model: 'bge-reranker' }],
  ['managed-rerank', 'Managed rerank API', 'Fusion', 'Retrieval', 'provider', 'Delegate reranking to a hosted API for strong quality without local GPU resources.', 'Hosted rerank endpoint with batch scoring.', ['reranking', 'api'], { model: 'rerank-v3', top_n: 10 }],
  // ── Selection & Filtering ──────────────────────────────────────────────────
  ['top-k', 'Top-K selection', 'Selection & Filtering', 'Retrieval', 'reference', 'Keep the highest-scoring K candidates before context assembly.', 'Sort by score and truncate.', ['selection', 'baseline'], { k: 5 }],
  ['mmr', 'Maximal marginal relevance', 'Selection & Filtering', 'Retrieval', 'reference', 'Balance relevance and diversity to avoid redundant context.', 'Iterative MMR selection against already chosen documents.', ['selection', 'diversity'], { lambda: 0.7, k: 5 }],
  ['token-budget-selection', 'Token-budget selection', 'Selection & Filtering', 'Retrieval', 'design', 'Select documents to fill a fixed token budget while preserving rank order.', 'Greedy packing with tokenizer-based accounting.', ['selection', 'budget'], { max_tokens: 2400 }],
  ['similarity-threshold', 'Similarity threshold filtering', 'Selection & Filtering', 'Retrieval', 'reference', 'Discard candidates below a minimum relevance score.', 'Score cutoff applied after retrieval and reranking.', ['filtering'], { min_score: 0.35 }],
  ['self-query-filtering', 'Self-query metadata filtering', 'Selection & Filtering', 'Retrieval', 'design', 'Translate natural-language constraints into structured metadata filters.', 'LLM extracts filter clauses validated against the schema.', ['filtering', 'query'], { strict: true }],
  ['contextual-compression', 'Contextual compression', 'Selection & Filtering', 'Retrieval', 'design', 'Extract only the sentences relevant to the query from each retrieved document.', 'Compressor model or extractive selector per candidate.', ['compression', 'precision'], { max_sentences: 3 }],
  // ── Context Processing ─────────────────────────────────────────────────────
  ['prompt-compaction', 'Prompt compaction', 'Context Processing', 'Generation', 'design', 'Compress retrieved context and conversation history to reduce prompt size.', 'LLM summarization with fact-preservation checks.', ['prompt', 'compression'], { target_tokens: 3000 }],
  ['long-context-reordering', 'Long-context reordering', 'Context Processing', 'Generation', 'design', 'Place the most relevant passages at the beginning and end of the prompt.', 'Rank-aware prompt layout to mitigate position bias.', ['prompt', 'position'], { strategy: 'edges' }],
  ['citation-annotation', 'Citation annotation', 'Context Processing', 'Generation', 'design', 'Inject stable source markers into context so generated claims can be traced.', 'Chunk IDs rendered as numbered citation tokens.', ['citations', 'prompt'], { style: '[n]' }],
  ['prompt-assembly', 'Contextual prompt assembly', 'Context Processing', 'Generation', 'reference', 'Compose system instructions, context and question into a grounded prompt.', 'Templated assembler with token-budget guardrails.', ['prompt'], { template: 'grounded-v2' }],
  ['lost-in-the-middle', 'Lost-in-the-middle mitigation', 'Context Processing', 'Generation', 'design', 'Rebalance context length and ordering to keep key evidence salient.', 'Evidence duplication plus targeted repositioning.', ['prompt', 'quality'], { duplicate_evidence: true }],
  // ── Validation ─────────────────────────────────────────────────────────────
  ['faithfulness-scoring', 'Faithfulness scoring', 'Validation', 'Evaluation', 'reference', 'Measure whether generated claims are supported by the retrieved context.', 'Claim extraction followed by NLI-based entailment check.', ['evaluation', 'ragas'], { threshold: 0.8 }],
  ['answer-relevance', 'Answer relevance grading', 'Validation', 'Evaluation', 'reference', 'Grade how well the answer addresses the original question.', 'LLM-as-judge with rubric-based scoring.', ['evaluation', 'llm'], { threshold: 0.8 }],
  ['hallucination-detection', 'Hallucination detection', 'Validation', 'Evaluation', 'design', 'Flag unsupported statements before returning an answer.', 'Self-check against retrieved evidence with abstention policy.', ['evaluation', 'safety'], { strict: true }],
  ['self-rag', 'Self-RAG reflection', 'Validation', 'Generation', 'design', 'Generate, critique and revise using reflection tokens for relevance and support.', 'Reflection-token guided iterative generation.', ['self-correction'], { max_iterations: 2 }],
  ['critic-correction', 'CRITIC self-correction', 'Validation', 'Generation', 'design', 'Use external tool feedback to verify and revise the generated answer.', 'Tool-grounded critique loop with revision.', ['self-correction', 'tools'], { max_iterations: 2 }],
  // ── Orchestration ──────────────────────────────────────────────────────────
  ['adaptive-routing', 'Adaptive RAG routing', 'Orchestration', 'Retrieval', 'design', 'Route each query to the retrieval strategy that fits its type and difficulty.', 'Query classifier selecting among dense, lexical or no-retrieval paths.', ['routing', 'query'], { routes: ['dense', 'hybrid', 'direct'] }],
  ['query-decomposition', 'Multi-step query decomposition', 'Orchestration', 'Retrieval', 'design', 'Break complex questions into sub-questions and combine their answers.', 'Planner generates sub-queries; executor runs them in sequence.', ['planning', 'multi-hop'], { max_steps: 4 }],
  ['agentic-tool-retrieval', 'Agentic tool retrieval', 'Orchestration', 'Retrieval', 'integration', 'Let an agent choose which tools or data sources to query at runtime.', 'Tool-calling loop with typed retrieval actions.', ['agent', 'tools'], { max_tool_calls: 6 }],
  ['corrective-rag', 'Corrective RAG (CRAG)', 'Orchestration', 'Retrieval', 'design', 'Evaluate retrieved documents and fall back to web or broader search when irrelevant.', 'Relevance evaluator triggering corrective retrieval actions.', ['fallback', 'routing'], { confidence_threshold: 0.5 }],
  ['retrieval-caching', 'Retrieval caching and memoization', 'Orchestration', 'Retrieval', 'integration', 'Cache embeddings, retrieval results and completions to cut latency and cost.', 'TTL cache keyed by normalized query and config hash.', ['operations', 'performance'], { ttl_seconds: 300 }],
  // ── Monitoring & Security ───────────────────────────────────────────────────
  ['drift-monitoring', 'Retrieval drift monitoring', 'Monitoring & Security', 'Evaluation', 'integration', 'Track ranking and score distributions to detect corpus or model drift.', 'Scheduled aggregate metrics over retrieval logs.', ['monitoring', 'operations'], { window_days: 7 }],
  ['pii-redaction', 'PII redaction', 'Monitoring & Security', 'Ingestion', 'provider', 'Detect and mask personally identifiable information before indexing.', 'Managed PII detector with reversible token vault.', ['security', 'privacy'], { entities: ['email', 'phone', 'ssn'] }],
  ['access-control-filtering', 'Access-control filtering', 'Monitoring & Security', 'Retrieval', 'integration', 'Enforce document-level permissions during retrieval, not after generation.', 'ACL predicates pushed into the vector store query.', ['security', 'filtering'], { enforce_at_query: true }],
  ['latency-cost-tracing', 'Latency and cost tracing', 'Monitoring & Security', 'Evaluation', 'integration', 'Instrument each stage with token, latency and cost telemetry.', 'OpenTelemetry spans aggregated per pipeline stage.', ['monitoring', 'tracing'], { sample_rate: 1.0 }],
]

export const techniqueCategoryOrder = [
  'Preprocessing',
  'Enrichment',
  'Indexing & Storage',
  'Fusion',
  'Selection & Filtering',
  'Context Processing',
  'Validation',
  'Orchestration',
  'Monitoring & Security',
]

export const techniques: Technique[] = seeds.map(
  ([id, name, category, phase, status, description, implementation, tags, parameters]) => ({
    id,
    name,
    category,
    phase,
    status,
    description,
    implementation,
    tags,
    parameters: parameters ?? {},
  }),
)

export const techniqueCategories = (): CategorySummary[] =>
  techniqueCategoryOrder
    .map((category) => {
      const items = techniques.filter((t) => t.category === category)
      const byStatus = Object.fromEntries(
        TECHNIQUE_STATUSES.map((status) => [status, items.filter((t) => t.status === status).length]),
      )
      return { category, count: items.length, byStatus }
    })
    .filter((summary) => summary.count > 0)

export const techniquePhases = (): PhaseSummary[] => {
  const phases = Array.from(new Set(techniques.map((t) => t.phase)))
  return phases.map((phase) => ({ phase, count: techniques.filter((t) => t.phase === phase).length }))
}

export const getTechnique = (id: string): Technique | undefined => techniques.find((t) => t.id === id)
