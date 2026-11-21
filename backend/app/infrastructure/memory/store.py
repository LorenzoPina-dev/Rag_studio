"""In-memory compatibility store for Phase 1/2 foundation.

Provides frontend-compatible seed data and basic mutations so the API can run
without external infrastructure. Replaced progressively by repositories,
services, engine runtime, workers, and artifact storage in later phases.
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.api.v1.schemas.models import (
    ActivityItem,
    AnswerMeta,
    ComparisonPoint,
    CustomNode,
    CustomNodeDependency,
    CustomNodeFile,
    CustomNodeParameter,
    CustomNodeTemplate,
    CustomNodeTestOutput,
    CustomNodeVersion,
    DashboardData,
    DashboardMetrics,
    DataSource,
    Dataset,
    DatasetMetrics,
    DatasetsData,
    EmbeddingInspector,
    EvaluationData,
    EvaluationMeta,
    EvaluationMetric,
    EvaluationRun,
    EvaluationRunRequest,
    EvaluationSettings,
    Execution,
    ExecutionResult,
    ExecutionRuntime,
    Experiment,
    ExperimentComparison,
    ExperimentCreateRequest,
    ExperimentData,
    ExperimentProject,
    ExperimentSummary,
    IngestionJob,
    LineageStep,
    LogEntry,
    Model,
    ModelBenchmark,
    ModelRegisterRequest,
    ModelResources,
    ModelTestResponse,
    ModelsData,
    NodeCatalogCategory,
    NodeDefinition,
    NodeOutputSummary,
    NodeRun,
    ParamDefinition,
    Pipeline,
    PipelineCreate,
    PipelineEdge,
    PipelineNode,
    PipelineSummary,
    PortDefinition,
    Project,
    ProjectCreate,
    Provider,
    QuestionResult,
    RetrievedDocument,
    RuntimeBreakdown,
    SearchResult,
    StepItem,
    StepMetric,
    StepOutput,
    SystemStatus,
    TestResult,
    TestRun,
    TrendPoint,
    ValidationIssue,
    ValidationResult,
    Workspace,
    XYPosition,
)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_time() -> str:
    return datetime.now().strftime("Today, %H:%M:%S")


# --- workspace/system ---
workspace = Workspace(id="ws_research", name="Research lab", plan="Team workspace", role="Owner")
system_status = SystemStatus(state="operational", version="v0.8.2", python="Python 3.12", connected=True, branch="main*", errors=0, warnings=0)

# --- projects/activity ---
projects: list[Project] = [
    Project(id="pr_knowledge", name="Knowledge assistant", description="Production-ready document Q&A", health="healthy", pipelineCount=8, chunkCount=24800, editedAt="2 hours ago", updatedAt=_now_iso(), accent="#7296FF"),
    Project(id="pr_research", name="Research copilot", description="Multi-source scientific retrieval", health="healthy", pipelineCount=5, chunkCount=12300, editedAt="2 hours ago", updatedAt=_now_iso(), accent="#A78BFA"),
    Project(id="pr_support", name="Support intelligence", description="Fast, grounded support answers", health="healthy", pipelineCount=4, chunkCount=8100, editedAt="2 hours ago", updatedAt=_now_iso(), accent="#35D99B"),
    Project(id="pr_multimodal", name="Multimodal document QA", description="Vision-aware document understanding", health="draft", pipelineCount=2, chunkCount=4100, editedAt="Yesterday", updatedAt=_now_iso(), accent="#E48EF0"),
]
activity: list[ActivityItem] = [
    ActivityItem(id="a1", title="Pipeline deployed", detail="Hybrid RAG pipeline · v2.4", time="12 min ago", type="pipeline"),
    ActivityItem(id="a2", title="Evaluation completed", detail="Faithfulness improved by 4.5%", time="38 min ago", type="evaluation"),
    ActivityItem(id="a3", title="Dataset synchronized", detail="product_docs · 12 new files", time="1 hour ago", type="dataset"),
    ActivityItem(id="a4", title="Custom node published", detail="Diversity-aware ranker · v1.2.0", time="2 hours ago", type="custom-node"),
]

# --- node registry/catalog ---
def _port(id: str, label: str, data_type: str, type_label: str, color: str, required: bool | None = None) -> PortDefinition:
    return PortDefinition(id=id, label=label, dataType=data_type, typeLabel=type_label, color=color, required=required)

def _param(key: str, label: str, ptype: str, default: Any, unit: str | None = None, help: str | None = None, options: list[str] | None = None) -> ParamDefinition:
    return ParamDefinition(key=key, label=label, type=ptype, defaultValue=default, unit=unit, help=help, options=options)

node_definitions: list[NodeDefinition] = [
    NodeDefinition(id="document-source", name="Document source", category="Data Sources", kind="source", description="Load documents from a connected dataset or file source.", summary="Load documents from a connected dataset or file source.", accent="#39D6D0", inputs=[], outputs=[_port("out_documents", "Documents", "documents", "Document[]", "#39D6D0")], params=[_param("dataset", "Dataset", "select", "product_docs", options=["product_docs", "research_papers", "support_knowledge"]), _param("fileTypes", "File types", "select", "all", options=["all", "pdf", "text", "txt", "md", "json", "jsonl", "csv", "documents", "other"], help="all | pdf | text | txt | md | json | jsonl | csv | documents | other"), _param("fileName", "File name contains", "text", "", help="Sottostringa o wildcard * nel nome/path, es. eni_*")], tags=["source", "ingestion"], version="1.0.0"),
    NodeDefinition(id="merge-documents", name="Merge documents", category="Document Processing", kind="merge", description="Combine two filtered document branches into one deduplicated stream.", summary="Combine PDF and text branches into one document stream.", accent="#A78BFA", inputs=[_port("in_documents_a", "Documents A", "documents", "Document[]", "#39D6D0"), _port("in_documents_b", "Documents B", "documents", "Document[]", "#39D6D0")], outputs=[_port("out_documents", "Documents", "documents", "Document[]", "#39D6D0")], params=[], tags=["merge", "hybrid"], version="1.0.0"),
    NodeDefinition(id="semantic-chunking", name="Semantic Chunking", category="Document Processing", kind="chunking", description="Split documents with fixed, recursive, sentence, token or parent-child chunking.", summary="Split documents with fixed, recursive, sentence, token or parent-child chunking.", accent="#A78BFA", inputs=[_port("in_documents", "Documents", "documents", "Document[]", "#39D6D0", True)], outputs=[_port("out_chunks", "Chunks", "chunks", "Chunk[]", "#A78BFA")], params=[_param("chunkStrategy", "Chunking strategy", "select", "fixed", options=["fixed", "recursive", "sentence", "token", "parent-child"], help="fixed | recursive | sentence | token | parent-child"), _param("chunk_size", "Chunk size", "number", 512, "tokens"), _param("overlap", "Overlap", "number", 50, "tokens")], tags=["chunking", "semantic"], version="1.1.0"),
    NodeDefinition(id="bge-embeddings", name="Hash embeddings (reference)", category="Embeddings", kind="embedding", description="Deterministic SHA-256 hash vectors (128 dimensions). Not a trained model.", summary="Hash embeddings (reference): SHA-256 into 128 buckets, no model.", accent="#7296FF", inputs=[_port("in_text", "Text or chunks", "chunks", "Chunk[]", "#A78BFA", True)], outputs=[_port("out_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF")], params=[_param("model", "Algorithm", "select", "hash-sha256-128", options=["hash-sha256-128"])], tags=["embedding", "hash", "reference"], version="1.1.0"),
    NodeDefinition(id="provider-embeddings", name="Model embeddings", category="Embeddings", kind="embedding", description="Real embeddings from Hugging Face, Ollama or OpenAI.", summary="Embed text with a real model selected by provider.", accent="#35D99B", inputs=[_port("in_text", "Text or chunks", "chunks", "Chunk[]", "#A78BFA", True)], outputs=[_port("out_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF")], params=[_param("provider", "Provider", "select", "auto", options=["auto", "huggingface", "ollama", "openai"]), _param("model", "Model", "text", "", help="Vuoto = modello predefinito del provider.")], tags=["embedding", "provider", "model"], version="1.0.0"),
    NodeDefinition(id="qdrant", name="In-memory index (reference)", category="Vector Databases", kind="vector-store", description="Python-dictionary index for the current run. No Qdrant server.", summary="In-memory reference index, no external vector database.", accent="#F0B45C", inputs=[_port("in_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF", True)], outputs=[_port("out_index", "Index", "json", "IndexRef", "#F0B45C")], params=[_param("collection", "Collection", "text", "product_docs"), _param("distance", "Distance", "select", "Cosine", options=["Cosine", "Dot", "Euclid"])], tags=["vector", "reference", "in-memory"], version="1.1.0"),
    NodeDefinition(id="query-input", name="Query input", category="Control Flow", kind="input", description="Accept a user query and pass it into the pipeline.", summary="Accept a user query and pass it into the pipeline.", accent="#39D6D0", inputs=[], outputs=[_port("out_query", "Query", "query", "Query", "#39D6D0")], params=[_param("placeholder", "Placeholder", "text", "Ask a question...")], tags=["input", "query"], version="1.0.0"),
    NodeDefinition(id="query-rewrite", name="Query rewrite", category="Retrieval", kind="control", description="Multi-query, decomposition or HyDE prompt expansion.", summary="Expand a query into variants with deterministic algorithms.", accent="#E48EF0", inputs=[_port("in_query", "Query", "query", "Query", "#39D6D0", True)], outputs=[_port("out_queries", "Queries", "query", "Query[]", "#39D6D0")], params=[_param("strategy", "Strategy", "select", "multi_query", options=["multi_query", "decompose", "hyde_prompt"]), _param("n", "Max variants", "number", 3)], tags=["retrieval", "query-expansion"], version="1.0.0"),
    NodeDefinition(id="hybrid-retrieval", name="Hybrid Retrieval", category="Retrieval", kind="retrieval", description="BM25, dense, RRF, MMR, multi-query, HyDE and configurable selection.", summary="Hybrid retrieval with fusion, expansion and selection algorithms.", accent="#F0B45C", inputs=[_port("in_query", "Query", "query", "Query", "#39D6D0", True), _port("in_index", "Index", "json", "IndexRef", "#F0B45C", True)], outputs=[_port("out_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C")], params=[_param("retrievalAlgorithm", "Retrieval algorithm", "select", "hybrid", options=["hybrid", "dense", "bm25", "rrf", "mmr", "multi_query", "decompose", "hyde_prompt"]), _param("top_k", "Top K", "number", 20), _param("alpha", "Dense weight / MMR lambda", "number", 0.7), _param("fusion", "Score fusion", "select", "rrf", options=["rrf", "linear"]), _param("selection", "Selection", "select", "top_k", options=["top_k", "threshold", "mmr", "diversity", "adaptive"]), _param("minScore", "Minimum score", "number", 0.0), _param("queryExpansion", "Query expansion", "select", "none", options=["none", "multi_query", "decompose", "hyde_prompt"]), _param("embeddingProvider", "Query embedding provider", "select", "reference", options=["reference", "auto", "huggingface", "ollama", "openai"]), _param("embeddingModel", "Query embedding model", "text", "")], tags=["retrieval", "hybrid"], version="1.1.0"),
    NodeDefinition(id="bge-reranker", name="Lexical reranker (reference)", category="Reranking", kind="reranking", description="Heuristic lexical/diversity rescoring. Not a cross-encoder model.", summary="Lexical heuristic reranker (reference), no model.", accent="#A78BFA", inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", True), _port("in_query", "Query", "query", "Query", "#39D6D0", True)], outputs=[_port("out_ranked", "Ranked", "documents", "RetrievedCandidate[]", "#A78BFA")], params=[_param("model", "Algorithm", "select", "lexical-heuristic", options=["lexical-heuristic"]), _param("rerankStrategy", "Reranking strategy", "select", "lexical", options=["lexical", "diversity", "none"]), _param("top_n", "Top N", "number", 5)], tags=["reranking", "reference"], version="1.1.0"),
    NodeDefinition(id="provider-reranker", name="Model reranker", category="Reranking", kind="reranking", description="Cross-encoder or LLM reranking from Hugging Face, Ollama or OpenAI.", summary="Rerank with a real model.", accent="#35D99B", inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", True), _port("in_query", "Query", "query", "Query", "#39D6D0", True)], outputs=[_port("out_ranked", "Ranked", "documents", "RetrievedCandidate[]", "#A78BFA")], params=[_param("provider", "Provider", "select", "auto", options=["auto", "huggingface", "ollama", "openai"]), _param("model", "Model", "text", ""), _param("top_n", "Top N", "number", 5)], tags=["reranking", "provider", "model"], version="1.0.0"),
    NodeDefinition(id="context-builder", name="Context builder", category="Retrieval", kind="context", description="Build concat, compact or numbered context within a character budget.", summary="Render a bounded prompt context from candidates.", accent="#F0B45C", inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", True)], outputs=[_port("out_context", "Context", "json", "Context", "#F0B45C")], params=[_param("strategy", "Strategy", "select", "numbered", options=["concat", "compact", "numbered"]), _param("maxChars", "Max characters", "number", 4000)], tags=["context", "retrieval"], version="1.0.0"),
    NodeDefinition(id="retrieval-eval", name="Retrieval eval", category="Reranking", kind="evaluation", description="Recall, precision, MRR, nDCG and hit rate for retrieved ids.", summary="Evaluate retrieval quality against relevant ids.", accent="#5B7CFA", inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", True)], outputs=[_port("out_metrics", "Metrics", "json", "Json", "#5B7CFA")], params=[_param("relevantIds", "Relevant ids", "text", ""), _param("k", "K", "number", 5)], tags=["evaluation", "retrieval"], version="1.0.0"),
    NodeDefinition(id="llm-generation", name="Extractive generation (reference)", category="LLM Generation", kind="generation", description="Extract and rank sentences from context. No language model is called.", summary="Extractive generation (reference), no LLM.", accent="#7296FF", inputs=[_port("in_context", "Context", "documents", "RetrievedCandidate[]", "#A78BFA", True), _port("in_query", "Query", "query", "Query", "#39D6D0", True)], outputs=[_port("out_answer", "Answer", "text", "GeneratedAnswer", "#7296FF")], params=[_param("model", "Algorithm", "select", "extractive-reference", options=["extractive-reference"]), _param("generationStrategy", "Generation strategy", "select", "extractive", options=["extractive", "first", "concise"]), _param("maxSentences", "Max sentences", "number", 3), _param("temperature", "Temperature", "number", 0.2)], tags=["llm", "generation", "reference"], version="1.1.0"),
    NodeDefinition(id="provider-generation", name="Model generation", category="LLM Generation", kind="generation", description="Grounded generation with a real Hugging Face, Ollama or OpenAI model.", summary="Generate answers with a real provider.", accent="#35D99B", inputs=[_port("in_context", "Context", "documents", "RetrievedCandidate[]", "#A78BFA", True), _port("in_query", "Query", "query", "Query", "#39D6D0", True)], outputs=[_port("out_answer", "Answer", "text", "GeneratedAnswer", "#7296FF")], params=[_param("provider", "Provider", "select", "auto", options=["auto", "huggingface", "ollama", "openai"]), _param("model", "Model", "text", ""), _param("contextStrategy", "Context strategy", "select", "numbered", options=["concat", "compact", "numbered"]), _param("maxContextChars", "Max context characters", "number", 4000), _param("temperature", "Temperature", "number", 0.2), _param("maxTokens", "Max tokens", "number", 512)], tags=["llm", "generation", "provider", "model"], version="1.0.0"),
]

_PARAM_TYPE_MAP = {
    "text": "text", "textarea": "textarea", "number": "number", "integer": "number",
    "float": "number", "boolean": "boolean", "select": "select", "multi_select": "select",
    "json": "textarea", "secret_ref": "text", "model_ref": "text", "dataset_ref": "text",
    "provider_ref": "text",
}


def _definition_default(value: Any) -> str | int | float | bool:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value


def extend_node_definitions_from_descriptors(descriptors: Any) -> int:
    """Add advanced node descriptors to the frontend-compatible catalog.

    Descriptors are duck-typed so this module does not import the component
    layer (which would create an import cycle through the dataset store).
    """
    added = 0
    for descriptor in descriptors:
        if any(existing.id == descriptor.id for existing in node_definitions):
            continue
        params = []
        for param in descriptor.params:
            ptype = str(getattr(param.ptype, "value", param.ptype))
            params.append(
                ParamDefinition(
                    key=param.key,
                    label=param.label,
                    type=_PARAM_TYPE_MAP.get(ptype, "text"),  # type: ignore[arg-type]
                    defaultValue=_definition_default(param.default),
                    help=param.help,
                    options=[str(option) for option in param.options] if param.options else None,
                )
            )
        node_definitions.append(
            NodeDefinition(
                id=descriptor.id,
                name=descriptor.name,
                category=descriptor.category,
                kind=descriptor.kind,
                description=descriptor.description,
                summary=descriptor.description,
                accent=descriptor.accent,
                inputs=[
                    PortDefinition(
                        id=port.id,
                        label=port.label,
                        dataType=port.dtype,  # type: ignore[arg-type]
                        typeLabel=port.tlabel,
                        color=port.color,
                        required=port.required,
                    )
                    for port in descriptor.inputs
                ],
                outputs=[
                    PortDefinition(
                        id=port.id,
                        label=port.label,
                        dataType=port.dtype,  # type: ignore[arg-type]
                        typeLabel=port.tlabel,
                        color=port.color,
                    )
                    for port in descriptor.outputs
                ],
                params=params,
                tags=list(descriptor.tags),
                version="1.0.0",
            )
        )
        added += 1
    return added


def get_node_catalog() -> list[NodeCatalogCategory]:
    desc = {
        "Data Sources": "Load and connect documents and datasets.",
        "Document Processing": "Parse, clean, chunk and transform content.",
        "Embeddings": "Create vector representations for search and retrieval.",
        "Vector Databases": "Index and persist embeddings for retrieval.",
        "Retrieval": "Find relevant candidates for a query.",
        "Reranking": "Improve ordering of retrieved candidates.",
        "LLM Generation": "Produce grounded answers and outputs.",
        "Control Flow": "Inputs and orchestration primitives.",
    }
    buckets: dict[str, list[NodeDefinition]] = {}
    for nd in node_definitions:
        buckets.setdefault(nd.category, []).append(nd)
    return [NodeCatalogCategory(category=c, description=desc.get(c, "Pipeline components."), nodes=nodes) for c, nodes in buckets.items()]

def _inst(def_id: str, nid: str, x: float, y: float, config: dict[str, Any] | None = None) -> PipelineNode:
    d = next(n for n in node_definitions if n.id == def_id)
    cfg = config if config is not None else {p.key: p.defaultValue for p in d.params}
    return PipelineNode(id=nid, definitionId=d.id, name=d.name, category=d.category, kind=d.kind, accent=d.accent, position=XYPosition(x=x, y=y), config=cfg, inputs=d.inputs, outputs=d.outputs, status="idle")

active_pipeline = Pipeline(
    id="pl_hybrid_rag",
    projectId="pr_knowledge",
    name="Hybrid RAG pipeline",
    description="Dense + sparse retrieval with reranking and grounded generation.",
    environment="Development",
    status="valid",
    version="v2.4",
    updatedAt=_now_iso(),
    nodes=[
        _inst("document-source", "n_document", 40, 120),
        _inst("semantic-chunking", "n_chunking", 260, 120),
        _inst("bge-embeddings", "n_embeddings", 480, 120),
        _inst("qdrant", "n_qdrant", 700, 120),
        _inst("query-input", "n_query", 40, 340),
        _inst("hybrid-retrieval", "n_hybrid", 480, 300),
        _inst("bge-reranker", "n_reranker", 700, 300),
        _inst("llm-generation", "n_llm", 920, 300),
    ],
    edges=[
        PipelineEdge(id="e1", source="n_document", target="n_chunking", sourceHandle="out_documents", targetHandle="in_documents", dataType="documents"),
        PipelineEdge(id="e2", source="n_chunking", target="n_embeddings", sourceHandle="out_chunks", targetHandle="in_text", dataType="chunks"),
        PipelineEdge(id="e3", source="n_embeddings", target="n_qdrant", sourceHandle="out_embedding", targetHandle="in_embedding", dataType="embedding"),
        PipelineEdge(id="e4", source="n_query", target="n_hybrid", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
        PipelineEdge(id="e5", source="n_qdrant", target="n_hybrid", sourceHandle="out_index", targetHandle="in_index", dataType="json"),
        PipelineEdge(id="e6", source="n_hybrid", target="n_reranker", sourceHandle="out_candidates", targetHandle="in_candidates", dataType="documents"),
        PipelineEdge(id="e7", source="n_query", target="n_reranker", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
        PipelineEdge(id="e8", source="n_reranker", target="n_llm", sourceHandle="out_ranked", targetHandle="in_context", dataType="documents"),
        PipelineEdge(id="e9", source="n_query", target="n_llm", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
    ],
)
created_pipelines: dict[str, Pipeline] = {}

# Pipeline che usa provider reali: i nodi "reference" restano disponibili per
# test deterministici, ma questa è la pipeline da usare con modelli veri.
real_model_pipeline = Pipeline(
    id="pl_real_rag",
    projectId="pr_knowledge",
    name="Real model RAG pipeline",
    description="Recursive chunking, real embeddings, hybrid retrieval, model reranking and grounded generation.",
    environment="Development",
    status="draft",
    version="v1.0",
    updatedAt=_now_iso(),
    nodes=[
        _inst("document-source", "rm_document", 40, 120),
        _inst("semantic-chunking", "rm_chunking", 260, 120, {"chunkStrategy": "recursive"}),
        _inst("provider-embeddings", "rm_embeddings", 480, 120, {"provider": "auto", "model": ""}),
        _inst("qdrant", "rm_index", 700, 120),
        _inst("query-input", "rm_query", 40, 340),
        _inst("hybrid-retrieval", "rm_hybrid", 480, 300, {"retrievalAlgorithm": "hybrid", "fusion": "rrf", "selection": "diversity", "embeddingProvider": "auto", "embeddingModel": ""}),
        _inst("provider-reranker", "rm_reranker", 700, 300, {"provider": "auto", "model": "", "top_n": 5}),
        _inst("provider-generation", "rm_llm", 920, 300, {"provider": "auto", "model": "", "contextStrategy": "numbered"}),
    ],
    edges=[
        PipelineEdge(id="rm_e1", source="rm_document", target="rm_chunking", sourceHandle="out_documents", targetHandle="in_documents", dataType="documents"),
        PipelineEdge(id="rm_e2", source="rm_chunking", target="rm_embeddings", sourceHandle="out_chunks", targetHandle="in_text", dataType="chunks"),
        PipelineEdge(id="rm_e3", source="rm_embeddings", target="rm_index", sourceHandle="out_embedding", targetHandle="in_embedding", dataType="embedding"),
        PipelineEdge(id="rm_e4", source="rm_query", target="rm_hybrid", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
        PipelineEdge(id="rm_e5", source="rm_index", target="rm_hybrid", sourceHandle="out_index", targetHandle="in_index", dataType="json"),
        PipelineEdge(id="rm_e6", source="rm_hybrid", target="rm_reranker", sourceHandle="out_candidates", targetHandle="in_candidates", dataType="documents"),
        PipelineEdge(id="rm_e7", source="rm_query", target="rm_reranker", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
        PipelineEdge(id="rm_e8", source="rm_reranker", target="rm_llm", sourceHandle="out_ranked", targetHandle="in_context", dataType="documents"),
        PipelineEdge(id="rm_e9", source="rm_query", target="rm_llm", sourceHandle="out_query", targetHandle="in_query", dataType="query"),
    ],
)
created_pipelines["pl_real_rag"] = real_model_pipeline


def _pipeline_summary(p: Pipeline, project_name: str = "Knowledge assistant", last_status: str | None = "passed", last_at: str | None = "2 min ago") -> PipelineSummary:
    return PipelineSummary(id=p.id, projectId=p.projectId, projectName=project_name, name=p.name, nodeCount=len(p.nodes), connectionCount=len(p.edges), status=p.status, environment=p.environment, updatedAt=p.updatedAt, lastRunStatus=last_status, lastRunAt=last_at)

def list_pipeline_summaries() -> list[PipelineSummary]:
    summaries = [
        _pipeline_summary(active_pipeline, next((pr.name for pr in projects if pr.id == active_pipeline.projectId), "Knowledge assistant"), "passed", "2 min ago"),
        PipelineSummary(id="pl_semantic_v2", projectId="pr_research", projectName="Research copilot", name="Semantic search v2", nodeCount=6, connectionCount=7, status="valid", environment="Production", updatedAt=_now_iso(), lastRunStatus="passed", lastRunAt="18 min ago"),
        PipelineSummary(id="pl_support_faq", projectId="pr_support", projectName="Support intelligence", name="Support FAQ retrieval", nodeCount=7, connectionCount=8, status="valid", environment="Production", updatedAt=_now_iso(), lastRunStatus="passed", lastRunAt="1 hour ago"),
        PipelineSummary(id="pl_multimodal", projectId="pr_knowledge", projectName="Knowledge assistant", name="Multimodal document QA", nodeCount=5, connectionCount=4, status="draft", environment="Development", updatedAt=_now_iso(), lastRunStatus="draft", lastRunAt="3 hours ago"),
    ]
    for p in reversed(list(created_pipelines.values())):
        summaries.insert(0, _pipeline_summary(p, next((pr.name for pr in projects if pr.id == p.projectId), "Knowledge assistant"), "draft", "never"))
    # dedupe by id preserving order
    seen = set()
    out = []
    for s in summaries:
        if s.id in seen: continue
        seen.add(s.id)
        out.append(s)
    return out

def get_pipeline(pid: str) -> Pipeline | None:
    if pid in created_pipelines:
        return created_pipelines[pid]
    if pid == active_pipeline.id:
        return active_pipeline
    if pid == "pl_semantic_v2":
        p = copy.deepcopy(active_pipeline)
        p.id = "pl_semantic_v2"; p.name = "Semantic search v2"; p.projectId = "pr_research"; p.environment = "Production"; p.version = "v1.8.0"
        return p
    if pid == "pl_support_faq":
        p = copy.deepcopy(active_pipeline); p.id = "pl_support_faq"; p.name = "Support FAQ retrieval"; p.projectId = "pr_support"; p.environment = "Production"; p.version = "v1.3.0"; return p
    if pid == "pl_multimodal":
        p = copy.deepcopy(active_pipeline); p.id = "pl_multimodal"; p.name = "Multimodal document QA"; p.projectId = "pr_knowledge"; p.environment = "Development"; p.status = "draft"; p.version = "v0.4.0"; p.nodes = p.nodes[:5]; p.edges = p.edges[:4]; return p
    return None

def save_pipeline(p: Pipeline) -> Pipeline:
    global active_pipeline
    p.updatedAt = _now_iso()
    if p.id == "pl_hybrid_rag" or (p.id == active_pipeline.id and p.id not in created_pipelines):
        active_pipeline = p
    else:
        created_pipelines[p.id] = p
    return p

def create_pipeline(req: PipelineCreate) -> Pipeline:
    pid = _id("pl")
    project_id = req.projectId or "pr_knowledge"
    nodes = []
    if req.template != "blank":
        nodes = [_inst("document-source", f"n_{pid}_1", 80, 80)]
    p = Pipeline(id=pid, projectId=project_id, name=req.name, description="A new retrieval-augmented generation pipeline.", environment="Development", status="draft", version="v0.1.0", updatedAt=_now_iso(), nodes=nodes, edges=[])
    created_pipelines[pid] = p
    return p

def validate_pipeline(p: Pipeline) -> ValidationResult:
    incoming = {e.target for e in p.edges}
    errors = [ValidationIssue(id=f"err_{i}", severity="error", message=f"Required input is not connected on '{n.name}'.", nodeId=n.id) for i, n in enumerate(n for n in p.nodes if n.inputs and n.id not in incoming)]
    gen = next((n for n in p.nodes if n.kind == "generation"), None)
    warnings = [ValidationIssue(id="warn_temp", severity="warning", message="LLM temperature is above 0 — answers may vary between runs.", nodeId=gen.id if gen else None)] if gen else []
    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings, checkedAt=_now_iso())

# --- executions ---
executions: list[Execution] = [
    Execution(id="run_2486", runNumber=2486, pipelineId="pl_hybrid_rag", pipelineName="Hybrid RAG pipeline", status="completed", startedAt="Today, 14:32:08", finishedAt="Today, 14:32:09", durationMs=1240, tokens=1842, cost=0.0062, environment="Development", trigger="Triggered manually", traceId="tr_8e4c92a1", errors=0, warnings=1, stagesCached=True,
        nodeRuns=[
            NodeRun(nodeId="n_document", name="Document source", kind="source", status="completed", durationMs=32, outputCount=248, accent="#39D6D0"),
            NodeRun(nodeId="n_chunking", name="Semantic Chunking", kind="chunking", status="completed", durationMs=138, outputCount=24816, accent="#A78BFA"),
            NodeRun(nodeId="n_embeddings", name="Hash embeddings (reference)", kind="embedding", status="completed", durationMs=86, outputCount=24816, accent="#7296FF"),
            NodeRun(nodeId="n_qdrant", name="Qdrant", kind="vector-store", status="completed", durationMs=64, outputCount=24816, accent="#F0B45C"),
            NodeRun(nodeId="n_query", name="Query input", kind="input", status="completed", durationMs=12, outputCount=1, accent="#39D6D0"),
            NodeRun(nodeId="n_hybrid", name="Hybrid Retrieval", kind="retrieval", status="completed", durationMs=124, outputCount=20, accent="#F0B45C"),
            NodeRun(nodeId="n_reranker", name="Lexical reranker (reference)", kind="reranking", status="completed", durationMs=181, outputCount=5, accent="#A78BFA"),
            NodeRun(nodeId="n_llm", name="LLM Generation", kind="generation", status="completed", durationMs=599, outputCount=1, accent="#7296FF"),
        ],
        logs=[LogEntry(id="l1", timestamp="14:32:08.000", level="INFO", message="Pipeline execution started: hybrid-rag-v2.4"), LogEntry(id="l7", timestamp="14:32:09.320", level="DONE", message="Pipeline completed successfully in 1.24s")]),
]

# Execution-scoped runtime state (real execution outputs/artifacts).
execution_inputs: dict[str, dict[str, dict[str, Any]]] = {}
execution_results: dict[str, ExecutionResult] = {}
execution_artifacts: dict[str, dict[str, Any]] = {}


def save_execution_result(result: ExecutionResult) -> ExecutionResult:
    execution_results[result.executionId] = result
    return result


def get_execution_result(execution_id: str) -> ExecutionResult | None:
    if execution_id in execution_results:
        return execution_results[execution_id]
    if execution_id == "run_2486":
        return execution_result_for(execution_id)
    return None


def save_execution_artifacts(execution_id: str, artifacts: dict[str, Any]) -> None:
    execution_artifacts[execution_id] = dict(artifacts)


def get_execution_artifact(execution_id: str, artifact_id: str) -> Any | None:
    return execution_artifacts.get(execution_id, {}).get(artifact_id)


def _next_run_number() -> int:
    return (max((e.runNumber for e in executions), default=2486) + 1)

def make_execution(p: Pipeline) -> Execution:
    rn = _next_run_number()
    node_runs = [NodeRun(nodeId=n.id, name=n.name, kind=n.kind, status="pending", durationMs=0, outputCount=(24816 if n.kind=="chunking" else 5 if n.kind=="reranking" else 20 if n.kind=="retrieval" else 1), accent=n.accent) for n in p.nodes]
    ex = Execution(id=f"run_{rn}", runNumber=rn, pipelineId=p.id, pipelineName=p.name, status="running", startedAt=_today_time(), durationMs=0, tokens=0, cost=0.0, environment=p.environment, trigger="Triggered manually", traceId=f"tr_{uuid.uuid4().hex[:8]}", errors=0, warnings=0, stagesCached=False, nodeRuns=node_runs, logs=[LogEntry(id=_id("log"), timestamp=datetime.now().strftime("%H:%M:%S.000"), level="INFO", message=f"Pipeline execution started: {p.name}")])
    executions.insert(0, ex)
    return ex

def get_execution(eid: str) -> Execution | None:
    return next((e for e in executions if e.id == eid), None)

def retrieved_docs() -> list[RetrievedDocument]:
    base = [
        ("Hybrid retrieval in RAG systems", "docs/guides/hybrid-retrieval.md", "chunk_0214", "Hybrid retrieval combines dense and sparse search to improve both semantic recall and exact keyword matching.", 0.964),
        ("Dense vector search fundamentals", "docs/guides/dense-search.md", "chunk_0188", "Dense retrieval encodes queries and chunks into embeddings and ranks candidates by vector similarity.", 0.947),
        ("BM25 and sparse retrieval", "docs/guides/bm25.md", "chunk_0132", "Sparse retrieval methods such as BM25 excel at lexical precision and keyword-heavy queries.", 0.931),
        ("Reciprocal rank fusion", "docs/guides/fusion.md", "chunk_0094", "RRF merges ranked lists from multiple retrievers without requiring calibrated scores.", 0.918),
        ("Reranking with cross-encoders", "docs/guides/reranking.md", "chunk_0301", "Cross-encoder rerankers jointly score query-document pairs for higher precision.", 0.902),
    ]
    return [RetrievedDocument(id=f"doc_{i}", rank=i, title=t, source=s, chunkId=c, excerpt=ex, content=ex+" This chunk preserves source metadata, offsets, and provenance for inspection.", score=sc, tokens=180+i*12, page=i, offset=f"{i*100}-{i*100+240}", mime="text/markdown") for i,(t,s,c,ex,sc) in enumerate(base,1)]

def _demo_step_outputs(docs: list[RetrievedDocument], query: str, answer: str) -> list[StepOutput]:
    def m(label: str, value: Any) -> StepMetric:
        return StepMetric(label=label, value=str(value))

    def doc_items(kind: str, limit: int = 6) -> list[StepItem]:
        items = []
        for index, doc in enumerate(docs[:limit], start=1):
            meta = {
                "fileType": doc.mime,
                "caratteri": len(doc.content),
                "punteggi": f"dense {doc.score:.3f}, sparse {max(0.1, doc.score - 0.08):.3f}",
                "rank": doc.rank,
                "chunk": doc.chunkId,
                "offset": doc.offset,
            }
            if kind == "chunking":
                meta["token"] = doc.tokens
                meta["documento"] = doc.title
            items.append(StepItem(id=f"{kind}_{index}", title=doc.title, source=doc.source, content=doc.content, meta=meta))
        return items

    return [
        StepOutput(
            nodeId="n_document",
            name="Document source",
            kind="source",
            detail="248 documenti",
            accent="#39D6D0",
            status="completed",
            durationMs=32,
            outputPorts=["out_documents"],
            items=doc_items("document"),
            metrics=[m("Documenti", "248"), m("Caratteri totali", "1.204.880"), m("Tipi file", "pdf: 193, md: 55")],
            searchHint="Cerca per documento, fonte o contenuto…",
        ),
        StepOutput(
            nodeId="n_chunking",
            name="Semantic Chunking",
            kind="chunking",
            detail="24.816 chunk",
            accent="#A78BFA",
            status="completed",
            durationMs=138,
            outputPorts=["out_chunks"],
            items=doc_items("chunk"),
            metrics=[m("Chunk", "24.816"), m("Token totali", "12.713.472"), m("Token medi", "512"), m("Documenti coperti", "248")],
            searchHint="Cerca per documento, fonte o testo del chunk…",
        ),
        StepOutput(
            nodeId="n_embeddings",
            name="Hash embeddings (reference, demo)",
            kind="embedding",
            detail="24.816 embedding",
            accent="#7296FF",
            status="completed",
            durationMs=86,
            outputPorts=["out_embedding"],
            items=doc_items("embedding", 3),
            metrics=[m("Embedding", "24.816"), m("Algoritmo", "hash-sha256-128"), m("Dimensioni", "128")],
            searchHint="Cerca per item, modello o vettore…",
        ),
        StepOutput(
            nodeId="n_qdrant",
            name="Qdrant",
            kind="vector-store",
            detail="24.816 vettori",
            accent="#F0B45C",
            status="completed",
            durationMs=64,
            outputPorts=["out_index"],
            items=[
                StepItem(
                    id="index_product_docs",
                    title="product_docs",
                    source="qdrant://product_docs",
                    content="Indice vettoriale pronto per il retrieval ibrido.",
                    meta={"collection": "product_docs", "distanza": "Cosine", "vettori": "24.816"},
                )
            ],
            metrics=[m("Vettori", "24.816"), m("Collection", "product_docs"), m("Distanza", "Cosine"), m("Dimensioni", "1.024")],
            searchHint="Cerca per collection o parametri dell’indice…",
        ),
        StepOutput(
            nodeId="n_query",
            name="Query input",
            kind="input",
            detail="1 query",
            accent="#39D6D0",
            status="completed",
            durationMs=12,
            outputPorts=["out_query"],
            text=query,
            metrics=[m("Caratteri", str(len(query))), m("Parole", str(len(query.split())))],
            searchHint="Cerca nella query…",
        ),
        StepOutput(
            nodeId="n_hybrid",
            name="Hybrid Retrieval",
            kind="retrieval",
            detail="20 candidati",
            accent="#F0B45C",
            status="completed",
            durationMs=124,
            outputPorts=["out_candidates"],
            items=doc_items("retrieval"),
            metrics=[m("Candidati", "20"), m("Score massimo", f"{docs[0].score:.4f}" if docs else "—"), m("Algoritmo", "hybrid")],
            searchHint="Cerca per documento, fonte o score…",
        ),
        StepOutput(
            nodeId="n_reranker",
            name="Lexical reranker (reference)",
            kind="reranking",
            detail="5 documenti selezionati",
            accent="#A78BFA",
            status="completed",
            durationMs=181,
            outputPorts=["out_ranked"],
            items=doc_items("reranked", 5),
            metrics=[m("Selezionati", "5"), m("Score massimo", f"{docs[0].score:.4f}" if docs else "—"), m("Strategia", "lexical")],
            searchHint="Cerca per documento, fonte o score…",
        ),
        StepOutput(
            nodeId="n_llm",
            name="Extractive generation (reference, demo)",
            kind="generation",
            detail="558 token",
            accent="#7296FF",
            status="completed",
            durationMs=599,
            outputPorts=["out_answer"],
            text=answer,
            items=[
                StepItem(id=f"cite_{index}", title=f"Citazione {index}", source=doc.source, content=doc.content, meta={})
                for index, doc in enumerate(docs[:5], start=1)
            ],
            metrics=[m("Token", "558"), m("Caratteri", str(len(answer))), m("Algoritmo", "extractive-reference"), m("Citazioni", "5")],
            searchHint="Cerca nelle citazioni…",
        ),
    ]


def _minimal_execution_result(ex: Execution) -> ExecutionResult:
    placeholder = RetrievedDocument(
        id="no_chunk",
        rank=0,
        title="No runtime result captured",
        source="",
        chunkId="",
        excerpt="",
        content="",
        score=0.0,
        tokens=0,
        page=0,
        offset="",
        mime="text/plain",
    )
    return ExecutionResult(
        id=f"res_{ex.id}",
        executionId=ex.id,
        query="No query captured",
        retrievedCount=0,
        selectedCount=0,
        errorCount=ex.errors,
        stages=[f"{len(ex.nodeRuns)} stages", "No runtime result captured"],
        traceId=ex.traceId,
        documents=[],
        chunk=placeholder,
        generatedAnswer="",
        answerMeta=AnswerMeta(model="reference", temperature=0.0, citations=0),
        lineage=[LineageStep(label=nr.name, detail=nr.status, indent=0, accent=nr.accent) for nr in ex.nodeRuns],
        nodeOutputs=[NodeOutputSummary(nodeId=nr.nodeId, name=nr.name, detail=f"{nr.outputCount:,} outputs", accent=nr.accent, kind=nr.kind) for nr in ex.nodeRuns],
        stepOutputs=[
            StepOutput(
                nodeId=nr.nodeId,
                name=nr.name,
                kind=nr.kind,
                detail=f"{nr.outputCount:,} output",
                accent=nr.accent,
                status=nr.status,
                durationMs=nr.durationMs,
                metrics=[StepMetric(label="Output", value=f"{nr.outputCount:,}"), StepMetric(label="Durata", value=f"{nr.durationMs} ms")],
                searchHint="Nessun output campione catturato per questa esecuzione.",
            )
            for nr in ex.nodeRuns
        ],
        embedding=EmbeddingInspector(model="reference", dimensions=0, cosineSimilarity=0.0, values=[], norm="0.0000", dtype="float32"),
        runtime=ExecutionRuntime(latencyMs=ex.durationMs, peakMemoryMb=0, tokensPerSecond=0, breakdown=[]),
    )


def execution_result_for(run_id: str) -> ExecutionResult:
    if run_id in execution_results:
        return execution_results[run_id]
    if run_id != "run_2486":
        ex = get_execution(run_id)
        if ex is None:
            raise KeyError(f"Execution not found: {run_id}")
        return _minimal_execution_result(ex)
    docs = retrieved_docs()
    query = "How does hybrid retrieval work?"
    answer = "Hybrid retrieval combines dense semantic search with sparse keyword search (e.g. BM25) and fuses their results, often with reciprocal rank fusion, before reranking to select the most relevant context for grounded generation."
    steps = _demo_step_outputs(docs, query, answer)
    details = {step.nodeId: step.detail for step in steps}
    node_outputs = [
        NodeOutputSummary(
            nodeId=nr.nodeId,
            name=nr.name,
            detail=details.get(nr.nodeId, nr.status),
            accent=nr.accent,
            kind=nr.kind,
            selected=nr.kind == "reranking",
        )
        for nr in get_execution(run_id).nodeRuns
    ]
    return ExecutionResult(
        id=f"res_{run_id}",
        executionId=run_id,
        query=query,
        retrievedCount=20,
        selectedCount=5,
        errorCount=0,
        stages=["6 stages", "Ingestion cached", "Trace ID tr_8e4c92a1"],
        traceId="tr_8e4c92a1",
        documents=docs,
        chunk=docs[0],
        generatedAnswer=answer,
        answerMeta=AnswerMeta(model="extractive-reference (demo)", temperature=0.2, citations=5),
        lineage=[LineageStep(label="product_docs", detail="248 documents", indent=0, accent="#39D6D0"), LineageStep(label="Semantic chunks", detail="24,816 chunks", indent=1), LineageStep(label="Hybrid retrieval", detail="20 retrieved", indent=1), LineageStep(label="Lexical reranker (reference)", detail="5 ranked", indent=2, accent="#35D99B")],
        nodeOutputs=node_outputs,
        stepOutputs=steps,
        embedding=EmbeddingInspector(model="hash-sha256-128 (reference, demo)", dimensions=128, cosineSimilarity=0.0, values=[0.5 + 0.4 * (((i * 7) % 17) / 16.0 - 0.5) for i in range(128)], norm="1.0000", dtype="float32"),
        runtime=ExecutionRuntime(latencyMs=1240, peakMemoryMb=428, tokensPerSecond=932, breakdown=[RuntimeBreakdown(label="Embedding", ms=86, color="#7296FF"), RuntimeBreakdown(label="Hybrid Retrieval", ms=124, color="#F0B45C"), RuntimeBreakdown(label="Lexical reranker (reference, demo)", ms=181, color="#35D99B"), RuntimeBreakdown(label="Extractive generation (reference, demo)", ms=599, color="#5B7CFA")]),
    )

# --- datasets ---
datasets: list[Dataset] = [
    Dataset(id="ds_product_docs", name="product_docs", sourceType="Local directory", format="PDF · Markdown", documents=248, chunks=24816, lastSync="2 min ago", status="indexed", path="/data/product_docs/", embedding="hash-sha256-128", chunking="Semantic · 512 tokens", usedBy=4, size="486 MB", health="healthy", documentsProcessed=248, documentsTotal=248),
    Dataset(id="ds_research_papers", name="research_papers", sourceType="S3", format="PDF · arXiv", documents=1420, chunks=68284, lastSync="24 min ago", status="indexed", path="s3://research-corpus/papers/", embedding="hash-sha256-128", chunking="Recursive · 512 tokens", usedBy=3, size="1.2 GB", health="healthy", documentsProcessed=1420, documentsTotal=1420),
    Dataset(id="ds_support_knowledge", name="support_knowledge", sourceType="Notion", format="Notion · HTML", documents=8642, chunks=52116, lastSync="1 hour ago", status="indexed", path="notion://support-kb", embedding="text-embedding-3-small", chunking="Semantic · 384 tokens", usedBy=2, size="842 MB", health="healthy", documentsProcessed=8642, documentsTotal=8642),
    Dataset(id="ds_customer_feedback", name="customer_feedback", sourceType="PostgreSQL", format="CSV · Text", documents=1912, chunks=20782, lastSync="Syncing…", status="ingesting", path="postgres://warehouse/feedback", embedding="text-embedding-3-small", chunking="Semantic · 512 tokens", usedBy=1, size="218 MB", health="warning", documentsProcessed=1402, documentsTotal=1912),
]
data_sources: list[DataSource] = [
    DataSource(id="src_local", name="Local workspace", type="Local files", status="connected", documents=1840, lastSync="2 min ago", config="2 directories", datasets=3),
    DataSource(id="src_aws", name="Research corpus", type="S3", status="connected", documents=1420, lastSync="24 min ago", config="s3://research-corpus", datasets=1),
    DataSource(id="src_notion", name="Support knowledge base", type="Notion", status="connected", documents=8642, lastSync="1 hour ago", config="Support workspace", datasets=1),
    DataSource(id="src_pg", name="Warehouse feedback", type="PostgreSQL", status="syncing", documents=1912, lastSync="Syncing…", config="warehouse.internal", datasets=1),
]
ingestion_jobs: list[IngestionJob] = [
    IngestionJob(id="job_1", datasetName="customer_feedback", status="running", progress=73, startedAt="2 min ago", duration="1m 42s", documents=1912, errors=0),
    IngestionJob(id="job_2", datasetName="product_docs", status="completed", progress=100, startedAt="6 min ago", duration="48s", documents=248, errors=0),
]

def datasets_data() -> DatasetsData:
    return DatasetsData(metrics=DatasetMetrics(connectedSources=len(data_sources), documents=sum(d.documents for d in datasets), documentsDelta="+248 in the last 24 hours", indexedChunks=sum(d.chunks for d in datasets), coverage="98.7% indexing coverage", storage="2.84 GB", capacity="18% of workspace capacity", sparks={"sources":[4,4,5,5,5,6,6,6,7,7,7,8],"documents":[22,26,25,30,36,34,41,46,44,52,58,64],"chunks":[18,20,19,24,28,27,32,36,35,40,45,48],"storage":[8,9,10,10,12,13,14,15,16,17,17,18]}), datasets=datasets, sources=data_sources, jobs=ingestion_jobs, connectors=["Local files","S3","Notion","Google Drive","Web crawl","PostgreSQL","REST API"])

# --- models ---
providers: list[Provider] = [Provider(id="openai", name="OpenAI", type="API provider", status="connected", models=3, detail="3 models available", accent="#39D6D0"), Provider(id="huggingface", name="Hugging Face", type="Local inference", status="connected", models=6, detail="6 models installed", accent="#F0B45C"), Provider(id="ollama", name="Ollama", type="Local runtime", status="connected", models=2, detail="2 models available", accent="#A78BFA")]
models: list[Model] = [
    Model(id="m_gpt4o", name="GPT-4o (API, not configured)", provider="OpenAI", type="Generation", context="128k tokens", status="idle", description="Real API model, available only after configuring OPENAI_API_KEY.", architecture="Transformer", parameters="Undisclosed", dimensions="—", maxSequence="128k tokens", precision="API managed", device="OpenAI API", memory="—", license="Proprietary", usedBy=8, local=False),
    Model(id="m_hash_reference", name="Hash embeddings (reference)", provider="RAG Studio", type="Embedding", context="—", status="idle", description="Deterministic SHA-256 token hashing into 128 buckets. Not a trained model.", architecture="Hash", parameters="—", dimensions="128", maxSequence="—", precision="float32", device="CPU · reference", memory="—", license="—", usedBy=12, benchmark=None, local=True),
    Model(id="m_lexical_reference", name="Lexical reranker (reference)", provider="RAG Studio", type="Reranking", context="—", status="idle", description="Lexical score heuristic over candidates. Not a cross-encoder.", architecture="Heuristic", parameters="—", dimensions="—", maxSequence="—", precision="—", device="CPU · reference", memory="—", license="—", usedBy=7, local=True),
    Model(id="m_llama", name="Llama 3.1 8B", provider="Ollama", type="Generation", context="128k tokens", status="idle", description="Local open-weights generation model.", architecture="Transformer", parameters="8B parameters", dimensions="—", maxSequence="128k tokens", precision="Q4_K_M", device="CUDA:0 · RTX 4090", memory="4.92 GB", license="Llama 3.1 Community", usedBy=3, local=True),
]

def models_data() -> ModelsData:
    return ModelsData(providers=providers, models=models, resources=ModelResources(gpu={"used":5.8,"total":24,"label":"5.8 / 24 GB"}, system={"used":4.2,"total":16,"label":"4.2 / 16 GB"}))

# --- evaluations ---
evaluation_state = EvaluationData(
    metrics=[EvaluationMetric(id="faithfulness", label="Faithfulness", value=0.92, delta="↑ 4.5% vs. baseline", trend="up"), EvaluationMetric(id="relevance", label="Answer relevance", value=0.89, delta="↑ 6.0% vs. baseline", trend="up"), EvaluationMetric(id="precision", label="Context precision", value=0.86, delta="↑ 7.5% vs. baseline", trend="up"), EvaluationMetric(id="recall", label="Context recall", value=0.94, delta="↑ 3.3% vs. baseline", trend="up")],
    trend=[TrendPoint(date="May 01", current=0.71, baseline=0.69), TrendPoint(date="May 11", current=0.79, baseline=0.74), TrendPoint(date="May 21", current=0.86, baseline=0.8), TrendPoint(date="May 26", current=0.92, baseline=0.87)],
    comparison=[ComparisonPoint(metric="Faithfulness", current=0.92, baseline=0.87), ComparisonPoint(metric="Relevance", current=0.89, baseline=0.84), ComparisonPoint(metric="Precision", current=0.86, baseline=0.79), ComparisonPoint(metric="Recall", current=0.94, baseline=0.88)],
    questions=[QuestionResult(id="q1", question="How does hybrid retrieval work?", faithfulness=0.98, relevance=0.96, contextPrecision=0.94, contextRecall=0.97, passed=True, reviewStatus="passed"), QuestionResult(id="q2", question="What embedding models are supported?", faithfulness=0.95, relevance=0.92, contextPrecision=0.9, contextRecall=0.93, passed=True, reviewStatus="passed"), QuestionResult(id="q4", question="What is the maximum document size?", faithfulness=0.71, relevance=0.74, contextPrecision=0.68, contextRecall=0.7, passed=False, reviewStatus="review")],
    meta=EvaluationMeta(pipeline="Hybrid RAG pipeline", dataset="rag_benchmark_v3", total=200, passed=192, failed=8, threshold=0.8, judge="GPT-4o", scorer="RAGAS 0.8.2", lastEvaluated="today at 14:35"),
    runs=[EvaluationRun(id="ev_1", label="rag_benchmark_v3", date="Today, 14:35", score=0.92, status="completed", questions=200)],
    settings=EvaluationSettings(passThreshold=0.8, sampleSize=200, judge="GPT-4o", autoRun=True, metricWeights={"faithfulness":0.4,"relevance":0.3,"precision":0.2,"recall":0.1}),
)

# --- experiments ---
experiments: list[Experiment] = [
    Experiment(id="exp_024", name="EXP-024 Hybrid + MMR", chunking="Semantic · 512", retrieval="Hybrid α0.7", selection="MMR · λ0.7", faithfulness=0.92, latency=1.24, cost=0.0062, status="complete", tags=["retrieval","best"], project="Knowledge assistant", createdAt="Today, 14:02"),
    Experiment(id="exp_023", name="EXP-023 BGE reranked", chunking="Semantic · 512", retrieval="Hybrid α0.5", selection="Top-K · 5", faithfulness=0.90, latency=1.18, cost=0.0056, status="complete", tags=["reranker"], project="Knowledge assistant", createdAt="Today, 13:48"),
    Experiment(id="exp_022", name="EXP-022 Baseline", chunking="Recursive · 512", retrieval="Dense only", selection="Top-K · 5", faithfulness=0.88, latency=0.82, cost=0.0048, status="complete", tags=["baseline"], project="Knowledge assistant", createdAt="Today, 13:31"),
    Experiment(id="exp_025", name="EXP-025 Custom ranking", chunking="Semantic · 768", retrieval="Hybrid α0.7", selection="DiversityRanker", faithfulness=None, latency=None, cost=None, status="running", tags=["custom-node"], project="Knowledge assistant", createdAt="Today, 14:28"),
]

def experiment_data() -> ExperimentData:
    return ExperimentData(project=ExperimentProject(name="Retrieval optimization", dataset="rag_benchmark_v3", questions=200), summary=ExperimentSummary(experiments=24, completed=21, running=2, bestScore=0.92), experiments=experiments, comparison=ExperimentComparison(ids=["exp_024","exp_023","exp_022"], parameters=[{"key":"Chunking","values":["Semantic","Semantic","Recursive"]},{"key":"Selection","values":["MMR","Top-K","Top-K"]},{"key":"Hybrid alpha","values":["0.7","0.5","0.0"]}], scatter=[{"id":"exp_024","name":"EXP-024","latency":1.24,"faithfulness":0.92,"accent":"#7296FF"},{"id":"exp_023","name":"EXP-023","latency":1.18,"faithfulness":0.90,"accent":"#A78BFA"},{"id":"exp_022","name":"EXP-022","latency":0.82,"faithfulness":0.88,"accent":"#35D99B"}], insight="EXP-024 delivers the best faithfulness (+4.5% vs baseline) with moderate latency."))

# --- custom nodes ---
custom_nodes: list[CustomNode] = [
    CustomNode(id="cn_diversity_ranker", name="Diversity-aware ranker", slug="diversity_ranker", category="Selection", description="Balances relevance and diversity when selecting retrieved candidates.", icon="sparkles", language="Python", files=[CustomNodeFile(id="f1", name="ranker.py", language="python", content="def rank(candidates, query, k=5, lambda_diversity=0.7):\n    return candidates[:k]\n"), CustomNodeFile(id="f2", name="config.yaml", language="yaml", content="name: diversity_ranker\nversion: 1.2.0\n")], parameters=[CustomNodeParameter(key="k", label="Top K", type="int", value=5), CustomNodeParameter(key="lambda_diversity", label="Lambda", type="float", value=0.7)], inputDefinitions=[PortDefinition(id="in_candidates", label="Candidates", dataType="documents", typeLabel="RetrievedCandidate[]", color="#F0B45C", required=True), PortDefinition(id="in_query", label="Query", dataType="query", typeLabel="Query", color="#39D6D0", required=True)], outputDefinitions=[PortDefinition(id="out_selected", label="Selected", dataType="documents", typeLabel="RetrievedCandidate[]", color="#35D99B")], dependencies=[CustomNodeDependency(name="numpy", version="1.26.4", installed=True), CustomNodeDependency(name="scikit-learn", version="1.5.0", installed=True)], versions=[CustomNodeVersion(id="v120", version="v1.2.0", label="Current draft", date="Today", author="Alex Morgan", changes="Improved diversity penalty and tests.", current=True), CustomNodeVersion(id="v110", version="v1.1.0", label="Published", date="Yesterday", author="Alex Morgan", changes="Initial MMR-style selection.")], updatedAt=_now_iso(), draftVersion="v1.2.0", basedOn="MMR selector template")
]

def custom_node_by_id(cid: str) -> CustomNode | None:
    return next((c for c in custom_nodes if c.id == cid), custom_nodes[0] if custom_nodes else None)


def create_custom_node(payload: CustomNode) -> CustomNode:
    for index, existing in enumerate(custom_nodes):
        if existing.id == payload.id:
            custom_nodes[index] = payload
            return payload
    custom_nodes.append(payload)
    return payload


def custom_node_test_output(cid: str) -> CustomNodeTestOutput:
    cn = custom_node_by_id(cid)
    return CustomNodeTestOutput(id=_id("test"), status="completed", nodeName=cn.name if cn else "Custom node", documents=retrieved_docs()[:3], diversityScore=0.83, durationMs=42, logs=["Loaded 20 candidates","Selected 5 diverse documents","Diversity score: 0.83"])

def custom_node_test_run(cid: str) -> TestRun:
    return TestRun(id=_id("testrun"), status="passed", tests=[TestResult(name="preserves_top_relevance", status="passed", durationMs=12), TestResult(name="improves_diversity", status="passed", durationMs=18)], summary="2/2 tests passed", metrics=[{"label":"Diversity","value":"0.83"},{"label":"Latency","value":"42ms"}], finishedAt=_today_time(), logs=["Running tests...","All tests passed"])

# --- dashboard/search ---
def dashboard() -> DashboardData:
    return DashboardData(
        metrics=DashboardMetrics(activeProjects=12, activeProjectsDelta="+2 this month", pipelines=38, pipelinesDelta="8 updated this week", executions=len(executions) or 2486, executionsDelta="↑ 18.6% vs. last week", faithfulness=0.92, faithfulnessDelta="↑ 0.04 vs. baseline", sparks={"projects":[3,4,5,6,7,8,9,10,11,12],"pipelines":[5,8,12,16,20,25,28,38],"executions":[8,12,18,23,28,31,34,38],"faithfulness":[6,8,11,14,16,17,20,23,26]}, resources={"memory":"4.2 / 16 GB","gpu":"NVIDIA RTX 4090 · 24 GB","storage":"82 GB available"}),
        projects=projects,
        pipelines=list_pipeline_summaries(),
        activity=activity,
    )

def search(q: str) -> list[SearchResult]:
    ql = q.lower().strip()
    if not ql:
        return []
    results: list[SearchResult] = []
    for p in projects:
        if ql in p.name.lower():
            results.append(SearchResult(id=p.id, type="project", title=p.name, subtitle=p.description, href="/projects"))
    for p in list_pipeline_summaries():
        if ql in p.name.lower():
            results.append(SearchResult(id=p.id, type="pipeline", title=p.name, subtitle=p.projectName, href=f"/pipelines/{p.id}"))
    for d in datasets:
        if ql in d.name.lower():
            results.append(SearchResult(id=d.id, type="dataset", title=d.name, subtitle=f"{d.documents:,} documents", href="/datasets"))
    for m in models:
        if ql in m.name.lower():
            results.append(SearchResult(id=m.id, type="model", title=m.name, subtitle=f"{m.provider} · {m.type}", href="/models"))
    for e in experiments:
        if ql in e.name.lower():
            results.append(SearchResult(id=e.id, type="experiment", title=e.name, subtitle=e.status, href="/experiments"))
    for n in node_definitions:
        if ql in n.name.lower():
            results.append(SearchResult(id=n.id, type="node", title=n.name, subtitle=n.category, href="/nodes"))
    return results[:20]
