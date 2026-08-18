from __future__ import annotations

import re
from dataclasses import dataclass, field

from archdiag.catalog import CATALOG, CONNECTION_LANGUAGE, SPECIFIC_DATABASES
from archdiag.render import render_svg
from archdiag.schema import (
    ArchitectureDiagram,
    Component,
    Connection,
    EvidenceSpan,
    TraceEvent,
)
from archdiag.telemetry import span as otel_span

_NUMBER_WORD = r"(?:two|three|four|five|six|seven|eight|nine|ten|\d+)"
_RESTRICT = re.compile(r"\b(?:only from|permitted only|restricted to|limited to)\b")
_CONNECTION_RE = re.compile("|".join(CONNECTION_LANGUAGE))
_HOST_KINDS = {
    "client",
    "application_server",
    "application_service",
    "load_balancer",
    "gateway",
    "firewall",
    "external_system",
    "proxy",
    "api",
}


@dataclass
class CatalogHit:
    id: str
    name: str
    kind: str
    zone: str
    pattern: str
    evidence: list[str] = field(default_factory=list)
    spans: list[EvidenceSpan] = field(default_factory=list)


class _TraceLog:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def add(
        self,
        action: str,
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
                action=action,  # type: ignore[arg-type]
                rule=rule,
                summary=summary,
                sentence_index=sentence_index,
                component_ids=component_ids or [],
                evidence=evidence,
            )
        )


def interpret_notes(notes: str) -> ArchitectureDiagram:
    text = " ".join(notes.split()).strip()
    if len(text) < 20:
        raise ValueError("Paste technical notes describing a system (at least a few sentences).")

    with otel_span("archdiag.interpret_notes", notes_chars=len(text)):
        sentences = _sentences(text)
        trace = _TraceLog()
        hits = _find_components(sentences)
        _prefer_specific_database(hits)
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
        connections, used_for_links = _find_connections(sentences, hits, trace)
        ambiguities = _ambiguities(sentences, hits, connections, trace)
        unused = [
            s
            for i, s in enumerate(sentences)
            if s not in used_for_links and not any(s in h.evidence for h in hits.values())
        ]
        for i, sentence in enumerate(sentences):
            if sentence in unused:
                trace.add(
                    "ignored_sentence",
                    "no_catalog_match",
                    "Sentence did not match catalog components or connection language.",
                    sentence_index=i,
                    evidence=sentence,
                )
        components = [
            Component(
                id=h.id,
                name=h.name,
                kind=h.kind,
                zone=h.zone,
                evidence=h.evidence,
                evidence_spans=h.spans,
                details=_details_for(h),
            )
            for h in hits.values()
        ]
        return ArchitectureDiagram(
            components=components,
            connections=connections,
            ambiguities=ambiguities,
            unused_sentences=unused,
            sentences=sentences,
            extraction_trace=trace.events,
            svg=render_svg(components, connections, ambiguities),
        )


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _find_components(sentences: list[str]) -> dict[str, CatalogHit]:
    found: dict[str, CatalogHit] = {}
    for index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        for cid, name, kind, zone, pattern in CATALOG:
            match = re.search(pattern, lowered)
            if not match:
                continue
            hit = found.setdefault(cid, CatalogHit(cid, name, kind, zone, pattern))
            if sentence not in hit.evidence:
                hit.evidence.append(sentence)
            span = EvidenceSpan(
                sentence_index=index,
                sentence=sentence,
                matched_text=match.group(0),
                rule=f"catalog:{cid}",
            )
            if span not in hit.spans:
                hit.spans.append(span)
    return found


def _prefer_specific_database(hits: dict[str, CatalogHit]) -> None:
    if any(name in hits for name in SPECIFIC_DATABASES):
        hits.pop("database", None)


def _mentioned_in(sentence: str, hits: dict[str, CatalogHit]) -> list[CatalogHit]:
    lowered = sentence.lower()
    found = [h for h in hits.values() if re.search(h.pattern, lowered)]
    found.sort(key=lambda h: _first_index(lowered, h.pattern))
    return found


def _first_index(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return match.start() if match else 10_000


def _has_connection_language(sentence: str) -> bool:
    return _CONNECTION_RE.search(sentence.lower()) is not None


def _find_connections(
    sentences: list[str],
    hits: dict[str, CatalogHit],
    trace: _TraceLog,
) -> tuple[list[Connection], set[str]]:
    used: set[str] = set()
    connections: list[Connection] = []
    seen: set[tuple[str, str]] = set()

    def add(
        src: str,
        dst: str,
        sentence: str,
        sentence_index: int,
        rule: str,
        confidence: str = "described",
    ) -> None:
        if src == dst or src not in hits or dst not in hits:
            return
        key = (src, dst)
        if key in seen:
            return
        seen.add(key)
        protocol = _protocol(sentence)
        port = _port(sentence)
        label_bits = [b for b in (protocol, f"port {port}" if port else None) if b]
        connections.append(
            Connection(
                source_id=src,
                target_id=dst,
                label=" · ".join(label_bits) if label_bits else "described flow",
                protocol=protocol,
                port=port,
                evidence=sentence,
                sentence_index=sentence_index,
                rule=rule,
                confidence=confidence,  # type: ignore[arg-type]
            )
        )
        used.add(sentence)
        trace.add(
            "linked_flow",
            rule,
            f"{hits[src].name} → {hits[dst].name}"
            + (f" ({', '.join(label_bits)})" if label_bits else ""),
            sentence_index=sentence_index,
            component_ids=[src, dst],
            evidence=sentence,
        )

    for sentence_index, sentence in enumerate(sentences):
        if not _has_connection_language(sentence):
            continue
        mentioned = _mentioned_in(sentence, hits)
        if len(mentioned) < 2:
            continue
        lowered = sentence.lower()
        ids = [m.id for m in mentioned]

        if "through" in lowered and len(ids) >= 3:
            for src, dst in zip(ids, ids[1:]):
                add(src, dst, sentence, sentence_index, "through_chain")
            continue
        if re.search(r"\bthen\b", lowered) and len(ids) >= 2:
            for src, dst in zip(ids, ids[1:]):
                add(src, dst, sentence, sentence_index, "then_chain")
            continue
        if re.search(r"\breceiv", lowered) and "from" in lowered:
            add(ids[-1], ids[0], sentence, sentence_index, "received_from")
            continue
        if "from" in lowered and "access" in lowered:
            add(ids[-1], ids[0], sentence, sentence_index, "access_from")
            continue
        if len(ids) >= 2:
            add(ids[0], ids[-1], sentence, sentence_index, "source_to_target")

    return connections, used


def _protocol(sentence: str) -> str | None:
    lowered = sentence.lower()
    for name in ("https", "http", "ssh", "tls", "tcp", "udp"):
        if re.search(rf"\b{name}\b", lowered):
            return name.upper()
    return None


def _port(sentence: str) -> str | None:
    match = re.search(r"port\s+(\d+)", sentence.lower())
    if match:
        return match.group(1)
    match = re.search(r":(\d{2,5})\b", sentence)
    return match.group(1) if match else None


def _details_for(hit: CatalogHit) -> list[str]:
    details: list[str] = []
    blob = " ".join(hit.evidence).lower()
    if re.search(rf"\b{_NUMBER_WORD}\s+(?:{hit.pattern})", blob) or re.search(
        rf"\ba number of\s+(?:{hit.pattern})", blob
    ):
        details.append(
            f"Count is given for {hit.name.lower()} but instances are not named individually "
            "(shown as one logical group)"
        )
    if re.search(r"\bports?\b", blob) and not re.search(r"port\s+\d+", blob):
        details.append("Ports were mentioned without numbers")
    quotes = sorted({span.matched_text for span in hit.spans})
    if quotes:
        details.append("Matched: " + ", ".join(f"“{q}”" for q in quotes))
    return details


def _ambiguities(
    sentences: list[str],
    hits: dict[str, CatalogHit],
    connections: list[Connection],
    trace: _TraceLog,
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(message: str, rule: str, sentence_index: int | None, evidence: str | None, ids: list[str]) -> None:
        if message in seen:
            return
        seen.add(message)
        items.append(message)
        trace.add(
            "flagged_ambiguity",
            rule,
            message,
            sentence_index=sentence_index,
            component_ids=ids,
            evidence=evidence,
        )

    for sentence_index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        if re.search(r"\bports?\b", lowered) and _port(sentence) is None:
            if "monitoring" in lowered:
                add(
                    "Monitoring ports are mentioned but no port numbers are given.",
                    "unnumbered_monitoring_ports",
                    sentence_index,
                    sentence,
                    ["monitoring"] if "monitoring" in hits else [],
                )
            else:
                add(
                    "A port is mentioned but no port number is given.",
                    "unnumbered_port",
                    sentence_index,
                    sentence,
                    [],
                )
        for hit in hits.values():
            numbered = re.search(rf"\b{_NUMBER_WORD}\s+(?:{hit.pattern})", lowered)
            numbered = numbered or re.search(rf"\ba number of\s+(?:{hit.pattern})", lowered)
            if numbered:
                add(
                    f"{hit.name} are mentioned as a numbered group but not named separately, "
                    "so they are drawn as one logical group.",
                    "unnamed_replicas",
                    sentence_index,
                    sentence,
                    [hit.id],
                )
        if _RESTRICT.search(lowered) and re.search(r"\baccess\b", lowered):
            mentioned = _mentioned_in(sentence, hits)
            host_sources = [h for h in mentioned if h.kind in _HOST_KINDS]
            zone_sources = [h for h in mentioned if h.kind in {"network_zone", "network"}]
            if zone_sources and not any(h.kind == "client" for h in host_sources):
                add(
                    "Access is limited to a network or zone; no source host is named.",
                    "zone_only_access",
                    sentence_index,
                    sentence,
                    [h.id for h in mentioned],
                )
            elif not mentioned:
                add(
                    "Access is restricted but no source system is named.",
                    "unnamed_access_source",
                    sentence_index,
                    sentence,
                    [],
                )

    if hits and not connections:
        add(
            "Components were found but no explicit connections could be extracted.",
            "components_without_flows",
            None,
            None,
            list(hits),
        )
    if not hits:
        add(
            "No known infrastructure components were recognised. "
            "The notes may use names that are not in the extractor catalog.",
            "empty_catalog",
            None,
            None,
            [],
        )
    return items
