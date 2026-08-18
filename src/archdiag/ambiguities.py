from __future__ import annotations

import re

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


class NoteAmbiguityFlagger:
    def flag(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        connections: list[Connection],
        trace: TraceLog,
    ) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()

        def add(
            message: str,
            rule: str,
            sentence_index: int | None,
            evidence: str | None,
            ids: list[str],
        ) -> None:
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
            if re.search(r"\bports?\b", lowered) and extract_port(sentence) is None:
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
                numbered = re.search(rf"\b{NUMBER_WORD}\s+(?:{hit.pattern})", lowered)
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
                mentioned = mentioned_in(sentence, hits)
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
