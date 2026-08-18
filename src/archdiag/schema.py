from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceSpan(BaseModel):
    """One quote from the notes that justified a component."""

    sentence_index: int
    sentence: str
    matched_text: str
    rule: str


class TraceEvent(BaseModel):
    """One auditable extraction decision (component, flow, skip, or ambiguity)."""

    event_id: str
    action: Literal[
        "matched_component",
        "linked_flow",
        "flagged_ambiguity",
        "ignored_sentence",
    ]
    rule: str
    summary: str
    sentence_index: int | None = None
    component_ids: list[str] = Field(default_factory=list)
    evidence: str | None = None


class Component(BaseModel):
    id: str
    name: str
    kind: str
    zone: str
    evidence: list[str] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


class Connection(BaseModel):
    source_id: str
    target_id: str
    label: str
    protocol: str | None = None
    port: str | None = None
    evidence: str
    sentence_index: int = 0
    rule: str = "source_to_target"
    confidence: Literal["described", "ambiguous"] = "described"


class ArchitectureDiagram(BaseModel):
    components: list[Component]
    connections: list[Connection]
    ambiguities: list[str]
    unused_sentences: list[str]
    sentences: list[str] = Field(default_factory=list)
    extraction_trace: list[TraceEvent] = Field(default_factory=list)
    svg: str
    disclaimer: str = (
        "This diagram only includes components and connections supported by the notes. "
        "Missing detail is listed as ambiguous rather than invented."
    )
