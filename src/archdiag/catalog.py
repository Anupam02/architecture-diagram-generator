"""Phrases recognised only when they actually appear in the notes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    kind: str
    zone: str
    pattern: str


def _e(cid: str, name: str, kind: str, zone: str, pattern: str) -> CatalogEntry:
    return CatalogEntry(cid, name, kind, zone, pattern)


CATALOG: tuple[CatalogEntry, ...] = (
    _e(
        "external-users",
        "Users / clients",
        "client",
        "external",
        r"external users|mobile clients?|end users?|"
        r"clients? (?:connect|reach|talk|call)|"
        r"(?:^|\b)users (?:connect|talk|reach|call)",
    ),
    _e("firewall", "Firewall", "firewall", "edge", r"\bfirewalls?\b"),
    _e("waf", "Web application firewall", "firewall", "edge", r"\bwaf\b|web application firewall"),
    _e(
        "load-balancer",
        "Load balancer",
        "load_balancer",
        "edge",
        r"load balancers?|\balb\b|\bnlb\b|\belb\b",
    ),
    _e(
        "app-servers",
        "Application servers",
        "application_server",
        "application",
        r"application servers?|backend servers?",
    ),
    _e("web-servers", "Web servers", "application_server", "application", r"web servers?"),
    _e("postgres", "PostgreSQL database", "database", "data", r"postgresql(?: database)?"),
    _e("mysql", "MySQL database", "database", "data", r"\bmysql\b"),
    _e("oracle", "Oracle database", "database", "data", r"\boracle(?: database)?"),
    _e("database", "Database", "database", "data", r"\bdatabases?\b"),
    _e("auth-service", "External authentication service", "external_system", "external", r"authentication service"),
    _e("identity-provider", "Identity provider", "external_system", "external", r"identity provider|\bidp\b|\bsso\b"),
    _e("monitoring", "External monitoring platform", "external_system", "external", r"monitoring platform"),
    _e("logging-service", "Logging service", "observability", "internal", r"logging service|log aggregat"),
    _e(
        "notification-service",
        "Notification service",
        "application_service",
        "application",
        r"notification service|notifier",
    ),
    _e("internal-network", "Internal network", "network_zone", "internal", r"internal network|dedicated network"),
    _e("dmz", "DMZ", "network_zone", "edge", r"\bdmz\b|demilitarized zone"),
    _e("api-gateway", "API gateway", "gateway", "edge", r"api gateway"),
    _e("payment-gateway", "Payment gateway", "gateway", "external", r"payment gateway"),
    _e("public-api", "API", "api", "application", r"rest api|\bhttp apis?\b|public api"),
    _e("cache", "Cache", "cache", "data", r"\bredis\b|\bmemcached\b|\bcache\b"),
    _e("object-storage", "Object storage", "storage", "data", r"\bs3\b|object storage"),
    _e("message-queue", "Message queue", "queue", "data", r"message queues?|\bkafka\b|\brabbitmq\b|\bsqs\b"),
    _e("cdn", "CDN", "cdn", "edge", r"\bcdn\b|content delivery network"),
    _e("vpn", "VPN", "network", "edge", r"\bvpn\b"),
    _e("dns", "DNS", "network", "edge", r"\bdns\b|name server"),
    _e("reverse-proxy", "Reverse proxy", "proxy", "edge", r"reverse proxy"),
)

CONNECTION_LANGUAGE = (
    r"\bconnect",
    r"\bcommunicate",
    r"\bdistribut",
    r"\baccess\b",
    r"\broute",
    r"\bsend",
    r"\btalk",
    r"\breach",
    r"\bforward",
    r"\bquer(?:y|ies|ied)\b",
    r"\bcalls?\b",
    r"\breceiv",
    r"\bhits?\b",
    r"\bthrough\b",
    r"\bthen\b",
)

SPECIFIC_DATABASES = ("postgres", "mysql", "oracle")
NUMBER_WORD = r"(?:two|three|four|five|six|seven|eight|nine|ten|\d+)"
ALLOWED_KINDS = {
    "client",
    "firewall",
    "load_balancer",
    "application_server",
    "application_service",
    "database",
    "external_system",
    "gateway",
    "cache",
    "storage",
    "queue",
    "cdn",
    "network",
    "proxy",
    "api",
    "network_zone",
    "observability",
}
ALLOWED_ZONES = {"external", "edge", "application", "data", "internal", "unspecified"}
