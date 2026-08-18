from __future__ import annotations

from dataclasses import dataclass

from archdiag.ambiguities import NoteAmbiguityFlagger
from archdiag.components import CatalogComponentFinder, drop_generic_database, hits_to_components
from archdiag.connections import RuleBasedConnectionLinker
from archdiag.llm import ConstrainedLlmMerger, NullProposer, proposer_from_env
from archdiag.models import TraceLog
from archdiag.ports import (
    AmbiguityFlagger,
    ComponentFinder,
    ConnectionLinker,
    DiagramRenderer,
    SpanProposer,
)
from archdiag.rendering import SvgRenderer
from archdiag.schema import ArchitectureDiagram
from archdiag.telemetry import span as otel_span
from archdiag.textutil import normalize_notes, split_sentences


@dataclass
class ArchitecturePipeline:
    """Orchestrates extraction. Dependencies are injected (Dependency Inversion)."""

    finder: ComponentFinder
    proposer: SpanProposer
    merger: ConstrainedLlmMerger
    linker: ConnectionLinker
    flagger: AmbiguityFlagger
    renderer: DiagramRenderer

    def run(self, notes: str) -> ArchitectureDiagram:
        text = normalize_notes(notes)
        if len(text) < 20:
            raise ValueError("Paste technical notes describing a system (at least a few sentences).")

        with otel_span(
            "archdiag.interpret_notes",
            notes_chars=len(text),
            llm_provider=self.proposer.provider_name,
        ):
            return self._run(text)

    def _run(self, text: str) -> ArchitectureDiagram:
        sentences = split_sentences(text)
        trace = TraceLog()
        hits = self.finder.find(sentences)
        proposals = self.proposer.propose(text, sentences)
        accepted, rejected = self.merger.merge(text, sentences, hits, proposals, trace)
        drop_generic_database(hits)

        for hit in hits.values():
            for ev in hit.spans:
                trace.add(
                    "matched_component",
                    ev.rule,
                    f"Recognised {hit.name!r} from {ev.matched_text!r}.",
                    sentence_index=ev.sentence_index,
                    component_ids=[hit.id],
                    evidence=ev.sentence,
                )

        connections, used_for_links = self.linker.link(sentences, hits, trace)
        ambiguities = self.flagger.flag(sentences, hits, connections, trace)
        unused = [
            sentence
            for sentence in sentences
            if sentence not in used_for_links and not any(sentence in h.evidence for h in hits.values())
        ]
        for index, sentence in enumerate(sentences):
            if sentence in unused:
                trace.add(
                    "ignored_sentence",
                    "no_catalog_match",
                    "Sentence did not match catalog components or connection language.",
                    sentence_index=index,
                    evidence=sentence,
                )
        components = hits_to_components(hits)
        return ArchitectureDiagram(
            components=components,
            connections=connections,
            ambiguities=ambiguities,
            unused_sentences=unused,
            sentences=sentences,
            extraction_trace=trace.events,
            llm_provider=self.proposer.provider_name,
            llm_accepted=accepted,
            llm_rejected=rejected,
            svg=self.renderer.render(components, connections, ambiguities),
        )


def default_pipeline(*, proposer: SpanProposer | None = None) -> ArchitecturePipeline:
    return ArchitecturePipeline(
        finder=CatalogComponentFinder(),
        proposer=proposer if proposer is not None else proposer_from_env(),
        merger=ConstrainedLlmMerger(),
        linker=RuleBasedConnectionLinker(),
        flagger=NoteAmbiguityFlagger(),
        renderer=SvgRenderer(),
    )


def interpret_notes(notes: str, *, proposer: SpanProposer | None = None) -> ArchitectureDiagram:
    """Public facade. Tests inject a proposer; production uses env (off by default)."""
    return default_pipeline(proposer=proposer).run(notes)


def catalog_only_pipeline() -> ArchitecturePipeline:
    return default_pipeline(proposer=NullProposer())
