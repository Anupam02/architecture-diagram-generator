from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Component(BaseModel):
    id: str
    name: str
    kind: str
    zone: str
    evidence: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


class Connection(BaseModel):
    source_id: str
    target_id: str
    label: str
    protocol: str | None = None
    port: str | None = None
    evidence: str
    confidence: Literal["described", "ambiguous"] = "described"


class ArchitectureDiagram(BaseModel):
    components: list[Component]
    connections: list[Connection]
    ambiguities: list[str]
    unused_sentences: list[str]
    svg: str
    disclaimer: str = (
        "This diagram only includes components and connections supported by the notes. "
        "Missing detail is listed as ambiguous rather than invented."
    )
