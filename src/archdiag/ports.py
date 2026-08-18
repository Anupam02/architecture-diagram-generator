"""Ports so the pipeline depends on abstractions, not a vendor LLM or SVG."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from archdiag.models import CatalogHit, TraceLog
from archdiag.schema import Component, Connection


@runtime_checkable
class ComponentFinder(Protocol):
    def find(self, sentences: list[str]) -> dict[str, CatalogHit]:
        ...


@runtime_checkable
class SpanProposer(Protocol):
    """Suggest extra component phrases. Must not be trusted until the verbatim gate."""

    provider_name: str

    def propose(self, notes: str, sentences: list[str]) -> list["ProposedComponent"]:
        ...


@runtime_checkable
class ConnectionLinker(Protocol):
    def link(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        trace: TraceLog,
    ) -> tuple[list[Connection], set[str]]:
        ...


@runtime_checkable
class AmbiguityFlagger(Protocol):
    def flag(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        connections: list[Connection],
        trace: TraceLog,
    ) -> list[str]:
        ...


@runtime_checkable
class DiagramRenderer(Protocol):
    def render(
        self,
        components: list[Component],
        connections: list[Connection],
        ambiguities: list[str],
    ) -> str:
        ...


class ProposedComponent:
    """DTO from a proposer. `phrase` is claimed to appear in the notes."""

    __slots__ = ("phrase", "name", "kind", "zone")

    def __init__(self, phrase: str, name: str, kind: str = "external_system", zone: str = "unspecified") -> None:
        self.phrase = phrase
        self.name = name
        self.kind = kind
        self.zone = zone
