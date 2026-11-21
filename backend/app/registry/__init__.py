"""Registries for nodes and providers (plugin/strategy resolution)."""

from .node_registry import NodeRegistration, NodeRegistry, node_registry
from .provider_registry import ProviderRegistration, ProviderRegistry, provider_registry

__all__ = [
    "NodeRegistration",
    "NodeRegistry",
    "ProviderRegistration",
    "ProviderRegistry",
    "node_registry",
    "provider_registry",
]
