from __future__ import annotations

import re

from archdiag.catalog import CATALOG, NUMBER_WORD, SPECIFIC_DATABASES, CatalogEntry
from archdiag.models import CatalogHit
from archdiag.schema import Component, EvidenceSpan
from archdiag.textutil import first_index


class CatalogComponentFinder:
    """Single responsibility: match catalog entries that actually occur in the notes."""

    def __init__(self, entries: tuple[CatalogEntry, ...] = CATALOG) -> None:
        self._entries = entries

    def find(self, sentences: list[str]) -> dict[str, CatalogHit]:
        found: dict[str, CatalogHit] = {}
        for index, sentence in enumerate(sentences):
            lowered = sentence.lower()
            for entry in self._entries:
                match = re.search(entry.pattern, lowered)
                if not match:
                    continue
                hit = found.setdefault(
                    entry.id,
                    CatalogHit(entry.id, entry.name, entry.kind, entry.zone, entry.pattern),
                )
                if sentence not in hit.evidence:
                    hit.evidence.append(sentence)
                span = EvidenceSpan(
                    sentence_index=index,
                    sentence=sentence,
                    matched_text=match.group(0),
                    rule=f"catalog:{entry.id}",
                )
                if span not in hit.spans:
                    hit.spans.append(span)
        drop_generic_database(found)
        return found


def drop_generic_database(hits: dict[str, CatalogHit]) -> None:
    if any(name in hits for name in SPECIFIC_DATABASES):
        hits.pop("database", None)


def mentioned_in(sentence: str, hits: dict[str, CatalogHit]) -> list[CatalogHit]:
    lowered = sentence.lower()
    found = [h for h in hits.values() if re.search(h.pattern, lowered)]
    found.sort(key=lambda h: first_index(lowered, h.pattern))
    return found


def details_for(hit: CatalogHit) -> list[str]:
    details: list[str] = []
    blob = " ".join(hit.evidence).lower()
    if re.search(rf"\b{NUMBER_WORD}\s+(?:{hit.pattern})", blob) or re.search(
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


def hits_to_components(hits: dict[str, CatalogHit]) -> list[Component]:
    return [
        Component(
            id=h.id,
            name=h.name,
            kind=h.kind,
            zone=h.zone,
            evidence=h.evidence,
            evidence_spans=h.spans,
            details=details_for(h),
        )
        for h in hits.values()
    ]
