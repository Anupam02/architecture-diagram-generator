from pathlib import Path

from archdiag.parse import interpret_notes

EXAMPLE = Path("sample_notes/exercise_example.txt").read_text(encoding="utf-8")
ALT = Path("sample_notes/api_gateway_cache.txt").read_text(encoding="utf-8")


def test_exercise_example_extracts_supported_components() -> None:
    model = interpret_notes(EXAMPLE)
    ids = {c.id for c in model.components}
    assert {
        "external-users",
        "firewall",
        "load-balancer",
        "app-servers",
        "postgres",
        "auth-service",
        "monitoring",
        "internal-network",
    } <= ids
    assert "cache" not in ids
    assert "vpn" not in ids


def test_exercise_example_connections_and_ports() -> None:
    model = interpret_notes(EXAMPLE)
    pairs = {(c.source_id, c.target_id) for c in model.connections}
    assert ("external-users", "firewall") in pairs
    assert ("firewall", "load-balancer") in pairs
    assert ("load-balancer", "app-servers") in pairs
    assert ("app-servers", "postgres") in pairs
    assert ("app-servers", "auth-service") in pairs
    assert ("monitoring", "app-servers") in pairs
    assert ("internal-network", "app-servers") in pairs
    ports = {c.port for c in model.connections if c.port}
    assert "443" in ports
    assert "5432" in ports
    assert any("monitoring ports" in a.lower() for a in model.ambiguities)
    assert "<svg" in model.svg


def test_does_not_invent_missing_products() -> None:
    model = interpret_notes(EXAMPLE)
    blob = " ".join(c.name.lower() for c in model.components)
    assert "redis" not in blob
    assert "kafka" not in blob


def test_second_sample_picks_up_named_components() -> None:
    model = interpret_notes(ALT)
    ids = {c.id for c in model.components}
    assert "api-gateway" in ids
    assert "cache" in ids
    assert "mysql" in ids
    assert "firewall" not in ids
    pairs = {(c.source_id, c.target_id) for c in model.connections}
    assert ("api-gateway", "app-servers") in pairs
    assert ("app-servers", "mysql") in pairs


def test_exercise_example_still_flags_three_ambiguities() -> None:
    model = interpret_notes(EXAMPLE)
    blob = " ".join(model.ambiguities).lower()
    assert "monitoring ports" in blob
    assert "application servers" in blob and "numbered group" in blob
    assert "network or zone" in blob or "internal network" in blob
    assert len(model.ambiguities) >= 3


def test_fresh_vocabulary_recognises_catalog_synonyms() -> None:
    notes = Path("sample_notes/fresh_vocabulary.txt").read_text(encoding="utf-8")
    model = interpret_notes(notes)
    ids = {c.id for c in model.components}
    assert "external-users" in ids
    assert "api-gateway" in ids
    assert "web-servers" in ids
    assert "mysql" in ids
    assert "payment-gateway" in ids
    assert "logging-service" in ids
    assert "app-servers" not in ids
    blob = " ".join(model.ambiguities).lower()
    assert "port" in blob and "number" in blob
    assert "web servers" in blob and "numbered group" in blob
    pairs = {(c.source_id, c.target_id) for c in model.connections}
    assert ("web-servers", "logging-service") in pairs


def test_extraction_trace_links_components_to_sentences() -> None:
    model = interpret_notes(EXAMPLE)
    assert model.sentences
    assert model.extraction_trace
    by_id = {c.id: c for c in model.components}
    firewall = by_id["firewall"]
    assert firewall.evidence_spans
    assert firewall.evidence_spans[0].matched_text == "firewall"
    assert "firewall" in model.sentences[firewall.evidence_spans[0].sentence_index].lower()
    rules = {c.rule for c in model.connections}
    assert "through_chain" in rules
    assert "access_from" in rules
    actions = {e.action for e in model.extraction_trace}
    assert "matched_component" in actions
    assert "linked_flow" in actions
    assert "flagged_ambiguity" in actions
    for conn in model.connections:
        assert 0 <= conn.sentence_index < len(model.sentences)
        assert conn.evidence == model.sentences[conn.sentence_index]


def test_users_talk_and_waf_then_chain() -> None:
    talk = interpret_notes("Users talk to a load balancer over HTTPS on port 443.")
    ids = {c.id for c in talk.components}
    assert "external-users" in ids
    assert "load-balancer" in ids
    assert ("external-users", "load-balancer") in {(c.source_id, c.target_id) for c in talk.connections}

    chain = interpret_notes(
        "Traffic hits a WAF then a load balancer then application servers."
    )
    ids = {c.id for c in chain.components}
    assert {"waf", "load-balancer", "app-servers"} <= ids
    pairs = {(c.source_id, c.target_id) for c in chain.connections}
    assert ("waf", "load-balancer") in pairs
    assert ("load-balancer", "app-servers") in pairs
    assert all(c.rule == "then_chain" for c in chain.connections)


def test_oracle_is_preferred_over_generic_database() -> None:
    model = interpret_notes(
        "Clients connect through a firewall to an Oracle database on port 1521."
    )
    ids = {c.id for c in model.components}
    assert "oracle" in ids
    assert "database" not in ids
    ports = {c.port for c in model.connections}
    assert "1521" in ports
    assert not any(e.component_ids == ["database"] for e in model.extraction_trace)

