from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from archdiag.catalog import NUMBER_WORD
from archdiag.components import mentioned_in
from archdiag.models import CatalogHit, TraceLog
from archdiag.schema import Connection
from archdiag.textutil import extract_port

_RESTRICT = re.compile(r"\b(?:only from|permitted only|restricted to|limited to)\b")
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


@dataclass(frozen=True)
class Finding:
    message: str
    rule: str
    sentence_index: int | None = None
    evidence: str | None = None
    component_ids: list[str] = field(default_factory=list)


class AmbiguityRule(Protocol):
    def collect(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        connections: list[Connection],
    ) -> list[Finding]:
        ...


class UnnumberedPorts:
    def collect(self, sentences, hits, connections) -> list[Finding]:
        found: list[Finding] = []
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            if not re.search(r"\bports?\b", lowered) or extract_port(sentence):
                continue
            if "monitoring" in lowered:
                found.append(
                    Finding(
                        "Monitoring ports are mentioned but no port numbers are given.",
                        "unnumbered_monitoring_ports",
                        index,
                        sentence,
                        ["monitoring"] if "monitoring" in hits else [],
                    )
                )
            else:
                found.append(
                    Finding(
                        "A port is mentioned but no port number is given.",
                        "unnumbered_port",
                        index,
                        sentence,
                        [],
                    )
                )
        return found


class UnnamedReplicas:
    def collect(self, sentences, hits, connections) -> list[Finding]:
        found: list[Finding] = []
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            for hit in hits.values():
                numbered = re.search(rf"\b{NUMBER_WORD}\s+(?:{hit.pattern})", lowered)
                numbered = numbered or re.search(rf"\ba number of\s+(?:{hit.pattern})", lowered)
                if numbered:
                    found.append(
                        Finding(
                            f"{hit.name} are mentioned as a numbered group but not named separately, "
                            "so they are drawn as one logical group.",
                            "unnamed_replicas",
                            index,
                            sentence,
                            [hit.id],
                        )
                    )
        return found


class RestrictedAccess:
    def collect(self, sentences, hits, connections) -> list[Finding]:
        found: list[Finding] = []
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            if not (_RESTRICT.search(lowered) and re.search(r"\baccess\b", lowered)):
                continue
            mentioned = mentioned_in(sentence, hits)
            host_sources = [h for h in mentioned if h.kind in _HOST_KINDS]
            zone_sources = [h for h in mentioned if h.kind in {"network_zone", "network"}]
            if zone_sources and not any(h.kind == "client" for h in host_sources):
                found.append(
                    Finding(
                        "Access is limited to a network or zone; no source host is named.",
                        "zone_only_access",
                        index,
                        sentence,
                        [h.id for h in mentioned],
                    )
                )
            elif not mentioned:
                found.append(
                    Finding(
                        "Access is restricted but no source system is named.",
                        "unnamed_access_source",
                        index,
                        sentence,
                        [],
                    )
                )
        return found


class MissingGraph:
    def collect(self, sentences, hits, connections) -> list[Finding]:
        if hits and not connections:
            return [
                Finding(
                    "Components were found but no explicit connections could be extracted.",
                    "components_without_flows",
                    None,
                    None,
                    list(hits),
                )
            ]
        if not hits:
            return [
                Finding(
                    "No known infrastructure components were recognised. "
                    "The notes may use names that are not in the extractor catalog.",
                    "empty_catalog",
                )
            ]
        return []


DEFAULT_AMBIGUITY_RULES: tuple[AmbiguityRule, ...] = (
    UnnumberedPorts(),
    UnnamedReplicas(),
    RestrictedAccess(),
    MissingGraph(),
)


class NoteAmbiguityFlagger:
    def __init__(self, rules: tuple[AmbiguityRule, ...] = DEFAULT_AMBIGUITY_RULES) -> None:
        self._rules = rules

    def flag(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        connections: list[Connection],
        trace: TraceLog,
    ) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for rule in self._rules:
            for finding in rule.collect(sentences, hits, connections):
                if finding.message in seen:
                    continue
                seen.add(finding.message)
                items.append(finding.message)
                trace.add(
                    "flagged_ambiguity",
                    finding.rule,
                    finding.message,
                    sentence_index=finding.sentence_index,
                    component_ids=finding.component_ids,
                    evidence=finding.evidence,
                )
        return items
