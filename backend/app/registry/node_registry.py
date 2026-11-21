"""Node registry: discovery and resolution of node implementations/specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

from app.domain.contracts.node import NodeImplementation, NodeSpec, NodeVersion


@dataclass
class NodeRegistration:
    spec: NodeSpec
    implementation: NodeImplementation | None = None
    version: NodeVersion | None = None
    source: str = "builtin"  # builtin|custom|plugin
    aliases: list[str] = field(default_factory=list)


class NodeRegistry:
    """In-memory registry for node definitions/implementations.

    Designed to be extended with plugin discovery (entry points/modules/packages)
    and custom-node loading from isolated metadata, without coupling the engine
    or API to concrete algorithms.
    """

    def __init__(self) -> None:
        self._registrations: Dict[str, NodeRegistration] = {}
        self._aliases: Dict[str, str] = {}

    def register_implementation(self, implementation: NodeImplementation, *, source: str = "builtin", aliases: Iterable[str] | None = None) -> NodeSpec:
        spec = implementation.spec()
        version = implementation.version()
        aliases = list(aliases or [])
        reg = NodeRegistration(spec=spec, implementation=implementation, version=version, source=source, aliases=aliases)
        self._registrations[spec.id] = reg
        for a in aliases:
            self._aliases[a] = spec.id
        return spec

    def register_spec(self, spec: NodeSpec, *, source: str = "builtin", aliases: Iterable[str] | None = None) -> NodeSpec:
        aliases = list(aliases or [])
        reg = self._registrations.get(spec.id)
        if reg:
            reg.spec = spec
            reg.source = source
            reg.aliases = aliases or reg.aliases
        else:
            reg = NodeRegistration(spec=spec, implementation=None, version=None, source=source, aliases=aliases)
            self._registrations[spec.id] = reg
        for a in reg.aliases:
            self._aliases[a] = spec.id
        return spec

    def attach_implementation(
        self,
        node_id: str,
        implementation: NodeImplementation,
        *,
        source: str | None = None,
    ) -> NodeSpec:
        """Attach an implementation to an existing spec (keeps the catalog spec).

        Useful when the API catalog is the source of truth for ports/params while
        the execution implementation lives elsewhere.
        """
        rid = self.resolve_id(node_id) or node_id
        reg = self._registrations.get(rid)
        version = implementation.version()
        if reg is None:
            spec = implementation.spec()
            self._registrations[spec.id] = NodeRegistration(
                spec=spec,
                implementation=implementation,
                version=version,
                source=source or "builtin",
            )
            return spec
        reg.implementation = implementation
        reg.version = version
        if source is not None:
            reg.source = source
        return reg.spec

    def resolve_id(self, node_id_or_alias: str) -> str | None:
        if node_id_or_alias in self._registrations:
            return node_id_or_alias
        return self._aliases.get(node_id_or_alias)

    def get(self, node_id: str) -> Optional[NodeRegistration]:
        rid = self.resolve_id(node_id)
        return self._registrations.get(rid) if rid else None

    def get_spec(self, node_id: str) -> Optional[NodeSpec]:
        reg = self.get(node_id)
        return reg.spec if reg else None

    def get_implementation(self, node_id: str) -> Optional[NodeImplementation]:
        reg = self.get(node_id)
        return reg.implementation if reg else None

    def list_specs(self) -> list[NodeSpec]:
        return [r.spec for r in self._registrations.values()]

    def list(self) -> list[NodeRegistration]:
        return list(self._registrations.values())

    def unregister(self, node_id: str) -> bool:
        rid = self.resolve_id(node_id)
        if not rid or rid not in self._registrations:
            return False
        reg = self._registrations.pop(rid)
        for a in reg.aliases:
            self._aliases.pop(a, None)
        return True


# Global/default registry instance (can be replaced/injected by composition root)
node_registry = NodeRegistry()
