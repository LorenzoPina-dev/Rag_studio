"""Algorithm/provider strategy interfaces.

Concrete implementations (recursive/semantic chunking, BM25/hybrid retrieval,
TopK/MMR selection, Ollama/OpenAI/Anthropic/Gemini, Qdrant/Chroma/FAISS, etc.)
must live outside domain core and be registered via provider/component registries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from app.domain.contracts.data import (
    Chunk,
    Context,
    Document,
    Embedding,
    EvaluationResult,
    GeneratedAnswer,
    Prompt,
    Query,
    RetrievedCandidate,
)


class Strategy(ABC):
    """Base marker for replaceable, configurable strategies."""

    id: str
    name: str
    version: str = "1.0.0"

    def validate_config(self, config: Mapping[str, Any]) -> list[str]:
        return []


class DocumentParser(Strategy):
    @abstractmethod
    async def parse(self, source: Any, config: Mapping[str, Any] | None = None) -> list[Document]:
        """Parse an input source into structured documents."""


class DocumentProcessor(Strategy):
    @abstractmethod
    async def process(self, documents: Sequence[Document], config: Mapping[str, Any] | None = None) -> list[Document]:
        """Transform/clean/enrich documents without losing provenance."""


class ChunkingStrategy(Strategy):
    @abstractmethod
    async def chunk(self, documents: Sequence[Document], config: Mapping[str, Any] | None = None) -> list[Chunk]:
        """Split documents into typed chunks preserving lineage/offsets."""


class EmbeddingProvider(Strategy):
    @abstractmethod
    async def embed_texts(self, texts: Sequence[str], config: Mapping[str, Any] | None = None) -> list[Embedding]:
        """Create embeddings for text inputs."""

    async def embed_query(self, query: str, config: Mapping[str, Any] | None = None) -> Embedding:
        results = await self.embed_texts([query], config=config)
        return results[0]


class VectorStore(Strategy):
    @abstractmethod
    async def upsert(self, embeddings: Sequence[Embedding], documents: Sequence[Chunk | Document] | None = None, config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Store embeddings/vectors and associated payloads."""

    @abstractmethod
    async def search(self, query_embedding: Embedding, top_k: int, config: Mapping[str, Any] | None = None) -> list[RetrievedCandidate]:
        """Search for nearest candidates by vector/query."""

    async def delete(self, ids: Sequence[str], config: Mapping[str, Any] | None = None) -> int:
        return 0


class Retriever(Strategy):
    @abstractmethod
    async def retrieve(self, query: Query, config: Mapping[str, Any] | None = None) -> list[RetrievedCandidate]:
        """Retrieve relevant candidates for a query (dense/sparse/hybrid/etc.)."""


class CandidateSelector(Strategy):
    @abstractmethod
    async def select(self, query: Query, candidates: Sequence[RetrievedCandidate], config: Mapping[str, Any] | None = None) -> list[RetrievedCandidate]:
        """Select candidates (Top-K/MMR/reward/adaptive/novelty/etc.) preserving scores/lineage."""


class Reranker(Strategy):
    @abstractmethod
    async def rerank(self, query: Query, candidates: Sequence[RetrievedCandidate], config: Mapping[str, Any] | None = None) -> list[RetrievedCandidate]:
        """Rescore and reorder candidates."""


class ContextBuilder(Strategy):
    @abstractmethod
    async def build(self, query: Query, candidates: Sequence[RetrievedCandidate], config: Mapping[str, Any] | None = None) -> Context:
        """Assemble selected candidates into a prompt-ready context."""


class LLMProvider(Strategy):
    @abstractmethod
    async def generate(self, prompt: Prompt | str, config: Mapping[str, Any] | None = None) -> GeneratedAnswer:
        """Generate a response from a prompt/context."""

    async def stream(self, prompt: Prompt | str, config: Mapping[str, Any] | None = None):
        """Optional streaming interface; implementations may yield chunks/events."""
        raise NotImplementedError


class OutputValidator(Strategy):
    @abstractmethod
    async def validate(self, answer: GeneratedAnswer, context: Context | None = None, config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Validate/score generated output (groundedness/format/safety checks)."""


class EvaluationMetric(Strategy):
    @abstractmethod
    async def evaluate(self, predictions: Sequence[Any], references: Sequence[Any] | None = None, config: Mapping[str, Any] | None = None) -> EvaluationResult | list[EvaluationResult]:
        """Compute evaluation metrics/results."""
