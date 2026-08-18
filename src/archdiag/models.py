"""Shared extraction types used across finders, linkers, and the LLM gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from archdiag.schema import EvidenceSpan, TraceAction, TraceEvent


@dataclass
class CatalogHit:
    id: str
    name: str
    kind: str
    zone: str
    pattern: str
    evidence: list[str] = field(default_factory=list)
    spans: list[EvidenceSpan] = field(default_factory=list)


class TraceLog:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def add(
        self,
        action: TraceAction,
        rule: str,
        summary: str,
        *,
        sentence_index: int | None = None,
        component_ids: list[str] | None = None,
        evidence: str | None = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                event_id=f"e{len(self.events) + 1}",
                action=action,
                rule=rule,
                summary=summary,
                sentence_index=sentence_index,
                component_ids=component_ids or [],
                evidence=evidence,
            )
        )
