"""Phrases recognised only when they actually appear in the notes."""

from __future__ import annotations

# id, display name, kind, zone, regex (matched against lowercased sentence)
CATALOG: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "external-users",
        "Users / clients",
        "client",
        "external",
        r"external users|mobile clients?|end users?|"
        r"clients? (?:connect|reach|talk|call)|"
        r"(?:^|\b)users (?:connect|talk|reach|call)",
    ),
    ("firewall", "Firewall", "firewall", "edge", r"\bfirewalls?\b"),
    ("waf", "Web application firewall", "firewall", "edge", r"\bwaf\b|web application firewall"),
    (
        "load-balancer",
        "Load balancer",
        "load_balancer",
        "edge",
        r"load balancers?|\balb\b|\bnlb\b|\belb\b",
    ),
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
    ("oracle", "Oracle database", "database", "data", r"\boracle(?: database)?"),
    ("database", "Database", "database", "data", r"\bdatabases?\b"),
    (
        "auth-service",
        "External authentication service",
        "external_system",
        "external",
        r"authentication service",
    ),
    (
        "identity-provider",
        "Identity provider",
        "external_system",
        "external",
        r"identity provider|\bidp\b|\bsso\b",
    ),
    (
        "monitoring",
        "External monitoring platform",
        "external_system",
        "external",
        r"monitoring platform",
    ),
    ("logging-service", "Logging service", "observability", "internal", r"logging service|log aggregat"),
    (
        "notification-service",
        "Notification service",
        "application_service",
        "application",
        r"notification service|notifier",
    ),
    (
        "internal-network",
        "Internal network",
        "network_zone",
        "internal",
        r"internal network|dedicated network",
    ),
    ("dmz", "DMZ", "network_zone", "edge", r"\bdmz\b|demilitarized zone"),
    ("api-gateway", "API gateway", "gateway", "edge", r"api gateway"),
    ("payment-gateway", "Payment gateway", "gateway", "external", r"payment gateway"),
    ("public-api", "API", "api", "application", r"rest api|\bhttp apis?\b|public api"),
    ("cache", "Cache", "cache", "data", r"\bredis\b|\bmemcached\b|\bcache\b"),
    ("object-storage", "Object storage", "storage", "data", r"\bs3\b|object storage"),
    (
        "message-queue",
        "Message queue",
        "queue",
        "data",
        r"message queues?|\bkafka\b|\brabbitmq\b|\bsqs\b",
    ),
    ("cdn", "CDN", "cdn", "edge", r"\bcdn\b|content delivery network"),
    ("vpn", "VPN", "network", "edge", r"\bvpn\b"),
    ("dns", "DNS", "network", "edge", r"\bdns\b|name server"),
    ("reverse-proxy", "Reverse proxy", "proxy", "edge", r"reverse proxy"),
)

# Word-boundary patterns — substring checks like "quer" in "required" are too noisy.
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
