from __future__ import annotations

import re
from dataclasses import dataclass, field

from archdiag.render import render_svg
from archdiag.schema import ArchitectureDiagram, Component, Connection

# Recognised only when the notes actually contain these phrases.
# The extractor will not add a component that does not match.
CATALOG: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "external-users",
        "Users / clients",
        "client",
        "external",
        r"external users|mobile clients?|end users?|clients? (?:connect|reach)|(?:^|\b)users connect",
    ),
    ("firewall", "Firewall", "firewall", "edge", r"\bfirewalls?\b"),
    ("load-balancer", "Load balancer", "load_balancer", "edge", r"load balancers?"),
    (
        "app-servers",
        "Application servers",
        "application_server",
        "application",
        r"application servers?|backend servers?",
    ),
    ("web-servers", "Web servers", "application_server", "application", r"web servers?"),
    ("postgres", "PostgreSQL database", "database", "data", r"postgresql(?: database)?"),
    ("mysql", "MySQL database", "database", "data", r"\bmysql\b"),
    ("database", "Database", "database", "data", r"\bdatabases?\b"),
    ("auth-service", "External authentication service", "external_system", "external", r"authentication service"),
    ("identity-provider", "Identity provider", "external_system", "external", r"identity provider|\bidp\b|\bsso\b"),
    ("monitoring", "External monitoring platform", "external_system", "external", r"monitoring platform"),
    ("logging-service", "Logging service", "observability", "internal", r"logging service|log aggregat"),
    (
        "notification-service",
        "Notification service",
        "application_service",
        "application",
        r"notification service|notifier",
    ),
    ("internal-network", "Internal network", "network_zone", "internal", r"internal network|dedicated network"),
    ("api-gateway", "API gateway", "gateway", "edge", r"api gateway"),
    ("payment-gateway", "Payment gateway", "gateway", "external", r"payment gateway"),
    ("cache", "Cache", "cache", "data", r"\bredis\b|\bmemcached\b|\bcache\b"),
    ("object-storage", "Object storage", "storage", "data", r"\bs3\b|object storage"),
    ("message-queue", "Message queue", "queue", "data", r"message queues?|\bkafka\b|\brabbitmq\b|\bsqs\b"),
    ("cdn", "CDN", "cdn", "edge", r"\bcdn\b|content delivery network"),
    ("vpn", "VPN", "network", "edge", r"\bvpn\b"),
    ("dns", "DNS", "network", "edge", r"\bdns\b|name server"),
    ("reverse-proxy", "Reverse proxy", "proxy", "edge", r"reverse proxy"),
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
    "forward",
    "quer",
    "call",
    "receiv",
)

_NUMBER_WORD = r"(?:two|three|four|five|six|seven|eight|nine|ten|\d+)"
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
}


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
    if re.search(rf"\b{_NUMBER_WORD}\s+(?:{hit.pattern})", blob) or re.search(
        rf"\ba number of\s+(?:{hit.pattern})", blob
    ):
        details.append(
            f"Count is given for {hit.name.lower()} but instances are not named individually "
            "(shown as one logical group)"
        )
    for port in re.findall(r"port\s+(\d+)", blob):
        details.append(f"Port mentioned: {port}")
    if "https" in blob:
        details.append("Protocol mentioned: HTTPS")
    if re.search(r"\bports?\b", blob) and not re.search(r"port\s+\d+", blob):
        details.append("Ports were mentioned without numbers")
    return details


def _ambiguities(
    sentences: list[str],
    hits: dict[str, CatalogHit],
    connections: list[Connection],
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(message: str) -> None:
        if message not in seen:
            seen.add(message)
            items.append(message)

    for sentence in sentences:
        lowered = sentence.lower()
        if re.search(r"\bports?\b", lowered) and _port(sentence) is None:
            if "monitoring" in lowered:
                add("Monitoring ports are mentioned but no port numbers are given.")
            else:
                add("A port is mentioned but no port number is given.")
        for hit in hits.values():
            numbered = re.search(rf"\b{_NUMBER_WORD}\s+(?:{hit.pattern})", lowered)
            numbered = numbered or re.search(rf"\ba number of\s+(?:{hit.pattern})", lowered)
            if numbered:
                add(
                    f"{hit.name} are mentioned as a numbered group but not named separately, "
                    "so they are drawn as one logical group."
                )
        if _RESTRICT.search(lowered) and re.search(r"\baccess\b", lowered):
            mentioned = _mentioned_in(sentence, hits)
            host_sources = [h for h in mentioned if h.kind in _HOST_KINDS]
            zone_sources = [h for h in mentioned if h.kind in {"network_zone", "network"}]
            if zone_sources and not any(h.kind == "client" for h in host_sources):
                add(
                    "Access is limited to a network or zone; no source host is named."
                )
            elif not mentioned:
                add("Access is restricted but no source system is named.")

    if hits and not connections:
        add("Components were found but no explicit connections could be extracted.")
    if not hits:
        add(
            "No known infrastructure components were recognised. "
            "The notes may use names that are not in the extractor catalog."
        )
    return items
