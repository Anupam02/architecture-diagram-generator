from __future__ import annotations

import re
from dataclasses import dataclass, field

from archdiag.render import render_svg
from archdiag.schema import ArchitectureDiagram, Component, Connection

# Recognised only when the notes actually contain these phrases.
# The extractor will not add a component that does not match.
CATALOG: tuple[tuple[str, str, str, str, str], ...] = (
    ("external-users", "External users", "client", "external", r"external users|(?:^|\b)users connect"),
    ("firewall", "Firewall", "firewall", "edge", r"\bfirewalls?\b"),
    ("load-balancer", "Load balancer", "load_balancer", "edge", r"load balancers?"),
    ("app-servers", "Application servers", "application_server", "application", r"application servers?"),
    ("postgres", "PostgreSQL database", "database", "data", r"postgresql(?: database)?"),
    ("mysql", "MySQL database", "database", "data", r"\bmysql\b"),
    ("database", "Database", "database", "data", r"\bdatabases?\b"),
    ("auth-service", "External authentication service", "external_system", "external", r"authentication service"),
    ("monitoring", "External monitoring platform", "external_system", "external", r"monitoring platform"),
    ("internal-network", "Internal network", "network_zone", "internal", r"internal network"),
    ("api-gateway", "API gateway", "gateway", "edge", r"api gateway"),
    ("cache", "Cache", "cache", "data", r"\bredis\b|\bmemcached\b|\bcache\b"),
    ("object-storage", "Object storage", "storage", "data", r"\bs3\b|object storage"),
    ("vpn", "VPN", "network", "edge", r"\bvpn\b"),
)

CONNECTION_VERBS = (
    "connect",
    "communicate",
    "distribut",
    "access",
    "route",
    "send",
    "talk",
    "reach",
)


@dataclass
class CatalogHit:
    id: str
    name: str
    kind: str
    zone: str
    pattern: str
    evidence: list[str] = field(default_factory=list)


def interpret_notes(notes: str) -> ArchitectureDiagram:
    text = " ".join(notes.split()).strip()
    if len(text) < 20:
        raise ValueError("Paste technical notes describing a system (at least a few sentences).")

    sentences = _sentences(text)
    hits = _find_components(sentences)
    _prefer_specific_database(hits)
    connections, used_for_links = _find_connections(sentences, hits)
    ambiguities = _ambiguities(sentences, hits, connections)
    unused = [
        s
        for s in sentences
        if s not in used_for_links and not any(s in h.evidence for h in hits.values())
    ]
    components = [
        Component(
            id=h.id,
            name=h.name,
            kind=h.kind,
            zone=h.zone,
            evidence=h.evidence,
            details=_details_for(h),
        )
        for h in hits.values()
    ]
    return ArchitectureDiagram(
        components=components,
        connections=connections,
        ambiguities=ambiguities,
        unused_sentences=unused,
        svg=render_svg(components, connections, ambiguities),
    )


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _find_components(sentences: list[str]) -> dict[str, CatalogHit]:
    found: dict[str, CatalogHit] = {}
    for sentence in sentences:
        lowered = sentence.lower()
        for cid, name, kind, zone, pattern in CATALOG:
            if re.search(pattern, lowered):
                hit = found.setdefault(
                    cid, CatalogHit(cid, name, kind, zone, pattern)
                )
                if sentence not in hit.evidence:
                    hit.evidence.append(sentence)
    return found


def _prefer_specific_database(hits: dict[str, CatalogHit]) -> None:
    if "postgres" in hits or "mysql" in hits:
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
    lowered = sentence.lower()
    return any(verb in lowered for verb in CONNECTION_VERBS) or "through" in lowered


def _find_connections(
    sentences: list[str],
    hits: dict[str, CatalogHit],
) -> tuple[list[Connection], set[str]]:
    used: set[str] = set()
    connections: list[Connection] = []
    seen: set[tuple[str, str]] = set()

    def add(src: str, dst: str, sentence: str, confidence: str = "described") -> None:
        if src == dst or src not in hits or dst not in hits:
            return
        key = (src, dst)
        if key in seen:
            return
        seen.add(key)
        protocol = _protocol(sentence)
        port = _port(sentence)
        if "required monitoring ports" in sentence.lower():
            port = None
        label_bits = [b for b in (protocol, f"port {port}" if port else None) if b]
        connections.append(
            Connection(
                source_id=src,
                target_id=dst,
                label=" · ".join(label_bits) if label_bits else "described flow",
                protocol=protocol,
                port=port,
                evidence=sentence,
                confidence=confidence,  # type: ignore[arg-type]
            )
        )
        used.add(sentence)

    for sentence in sentences:
        if not _has_connection_language(sentence):
            continue
        mentioned = _mentioned_in(sentence, hits)
        if len(mentioned) < 2:
            continue
        lowered = sentence.lower()
        ids = [m.id for m in mentioned]

        if "through" in lowered and len(ids) >= 3:
            add(ids[0], ids[1], sentence)
            add(ids[1], ids[2], sentence)
            continue
        if "from" in lowered and "access" in lowered:
            # "access to Y ... from X" → X -> Y
            add(ids[-1], ids[0], sentence)
            continue
        if len(ids) >= 2:
            add(ids[0], ids[-1], sentence)

    return connections, used


def _protocol(sentence: str) -> str | None:
    lowered = sentence.lower()
    for name in ("https", "http", "ssh", "tls", "tcp", "udp"):
        if re.search(rf"\b{name}\b", lowered):
            return name.upper()
    return None


def _port(sentence: str) -> str | None:
    match = re.search(r"port\s+(\d+)", sentence.lower())
    return match.group(1) if match else None


def _details_for(hit: CatalogHit) -> list[str]:
    details: list[str] = []
    blob = " ".join(hit.evidence).lower()
    if hit.id == "app-servers" and re.search(r"two application servers", blob):
        details.append("Count: two (shown as one logical group; not named individually)")
    for port in re.findall(r"port\s+(\d+)", blob):
        details.append(f"Port mentioned: {port}")
    if "https" in blob:
        details.append("Protocol mentioned: HTTPS")
    if "required monitoring ports" in blob:
        details.append("Monitoring ports were not numbered")
    return details


def _ambiguities(
    sentences: list[str],
    hits: dict[str, CatalogHit],
    connections: list[Connection],
) -> list[str]:
    items: list[str] = []
    blob = " ".join(s.lower() for s in sentences)
    if "required monitoring ports" in blob:
        items.append("Monitoring ports are mentioned but no port numbers are given.")
    if "two application servers" in blob:
        items.append(
            "Two application servers are mentioned but not named separately, so they are drawn as one logical group."
        )
    if "administrative access" in blob and "internal network" in blob:
        items.append(
            "Admin access is limited to the internal network; no admin workstation host is named."
        )
    if hits and not connections:
        items.append("Components were found but no explicit connections could be extracted.")
    if not hits:
        items.append(
            "No known infrastructure components were recognised. "
            "The notes may use names that are not in the extractor catalog."
        )
    return items
