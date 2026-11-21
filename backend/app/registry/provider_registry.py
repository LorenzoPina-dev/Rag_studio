"""Provider registry: resolution of algorithm/provider adapters by kind and id."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional

from app.domain.interfaces.strategies import Strategy


@dataclass
class ProviderRegistration:
    kind: str  # e.g. embedding, llm, vector_store, retriever, reranker, chunking
    provider_id: str
    implementation: Strategy | Any
    name: str | None = None
    version: str | None = None
    capabilities: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderRegistry:
    """Registry for pluggable provider/strategy implementations.

    Keys are (kind, provider_id). The DAG engine and application services resolve
    providers through this abstraction, keeping core logic algorithm-agnostic.
    """

    def __init__(self) -> None:
        self._providers: Dict[tuple[str, str], ProviderRegistration] = {}

    @staticmethod
    def _key(kind: str, provider_id: str) -> tuple[str, str]:
        return (kind.lower().strip(), provider_id)

    def register(
        self,
        kind: str,
        provider_id: str,
        implementation: Strategy | Any,
        *,
        name: str | None = None,
        version: str | None = None,
        capabilities: Iterable[str] | None = None,
        config_schema: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderRegistration:
        reg = ProviderRegistration(
            kind=kind.lower().strip(),
            provider_id=provider_id,
            implementation=implementation,
            name=name or getattr(implementation, "name", provider_id),
            version=version or getattr(implementation, "version", None),
            capabilities=list(capabilities or []),
            config_schema=dict(config_schema or {}),
            metadata=dict(metadata or {}),
        )
        self._providers[self._key(kind, provider_id)] = reg
        return reg

    def get(self, kind: str, provider_id: str) -> Optional[ProviderRegistration]:
        return self._providers.get(self._key(kind, provider_id))

    def resolve(self, kind: str, provider_id: str) -> Any | None:
        reg = self.get(kind, provider_id)
        return reg.implementation if reg else None

    def list(self, kind: str | None = None) -> list[ProviderRegistration]:
        if kind is None:
            return list(self._providers.values())
        k = kind.lower().strip()
        return [r for r in self._providers.values() if r.kind == k]

    def kinds(self) -> list[str]:
        return sorted({r.kind for r in self._providers.values()})

    def unregister(self, kind: str, provider_id: str) -> bool:
        return self._providers.pop(self._key(kind, provider_id), None) is not None


# Global/default registry instance (can be replaced/injected by composition root)
provider_registry = ProviderRegistry()
