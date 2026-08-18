"""Connection rules are open for extension: add a class, append it to RULES."""

from __future__ import annotations

import re
from typing import Protocol

from archdiag.catalog import CONNECTION_LANGUAGE
from archdiag.components import mentioned_in
from archdiag.models import CatalogHit, TraceLog
from archdiag.schema import Connection
from archdiag.textutil import extract_port, extract_protocol

_CONNECTION_RE = re.compile("|".join(CONNECTION_LANGUAGE))


class ConnectionRule(Protocol):
    name: str

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        """Return directed pairs, or None to try the next rule."""


class ThroughChain:
    name = "through_chain"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        if "through" in sentence.lower() and len(ids) >= 3:
            return list(zip(ids, ids[1:]))
        return None


class ThenChain:
    name = "then_chain"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        if re.search(r"\bthen\b", sentence.lower()) and len(ids) >= 2:
            return list(zip(ids, ids[1:]))
        return None


class ReceivedFrom:
    name = "received_from"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        if re.search(r"\breceiv", sentence.lower()) and "from" in sentence.lower() and len(ids) >= 2:
            return [(ids[-1], ids[0])]
        return None


class AccessFrom:
    name = "access_from"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        lowered = sentence.lower()
        if "from" in lowered and "access" in lowered and len(ids) >= 2:
            return [(ids[-1], ids[0])]
        return None


class SourceToTarget:
    name = "source_to_target"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        if len(ids) >= 2:
            return [(ids[0], ids[-1])]
        return None


DEFAULT_RULES: tuple[ConnectionRule, ...] = (
    ThroughChain(),
    ThenChain(),
    ReceivedFrom(),
    AccessFrom(),
    SourceToTarget(),
)


class RuleBasedConnectionLinker:
    def __init__(self, rules: tuple[ConnectionRule, ...] = DEFAULT_RULES) -> None:
        self._rules = rules

    def link(
        self,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        trace: TraceLog,
    ) -> tuple[list[Connection], set[str]]:
        used: set[str] = set()
        connections: list[Connection] = []
        seen: set[tuple[str, str]] = set()

        for sentence_index, sentence in enumerate(sentences):
            if not _CONNECTION_RE.search(sentence.lower()):
                continue
            mentioned = mentioned_in(sentence, hits)
            if len(mentioned) < 2:
                continue
            ids = [m.id for m in mentioned]
            chosen: list[tuple[str, str]] | None = None
            rule_name = "source_to_target"
            for rule in self._rules:
                result = rule.pairs(ids, sentence)
                if result is not None:
                    chosen = result
                    rule_name = rule.name
                    break
            if not chosen:
                continue
            for src, dst in chosen:
                added = _append_connection(
                    connections,
                    seen,
                    hits,
                    src,
                    dst,
                    sentence,
                    sentence_index,
                    rule_name,
                    trace,
                )
                if added:
                    used.add(sentence)
        return connections, used


def _append_connection(
    connections: list[Connection],
    seen: set[tuple[str, str]],
    hits: dict[str, CatalogHit],
    src: str,
    dst: str,
    sentence: str,
    sentence_index: int,
    rule: str,
    trace: TraceLog,
) -> bool:
    if src == dst or src not in hits or dst not in hits:
        return False
    key = (src, dst)
    if key in seen:
        return False
    seen.add(key)
    protocol = extract_protocol(sentence)
    port = extract_port(sentence)
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
        )
    )
    trace.add(
        "linked_flow",
        rule,
        f"{hits[src].name} → {hits[dst].name}"
        + (f" ({', '.join(label_bits)})" if label_bits else ""),
        sentence_index=sentence_index,
        component_ids=[src, dst],
        evidence=sentence,
    )
    return True
