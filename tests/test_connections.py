from archdiag.connections import RuleBasedConnectionLinker, SourceToTarget
from archdiag.models import CatalogHit, TraceLog


class FirstTwoOnly:
    name = "first_two"

    def pairs(self, ids: list[str], sentence: str) -> list[tuple[str, str]] | None:
        if len(ids) >= 2:
            return [(ids[0], ids[1])]
        return None


def test_connection_linker_is_open_for_new_rules() -> None:
    hits = {
        "a": CatalogHit("a", "A", "gateway", "edge", r"\ba\b"),
        "b": CatalogHit("b", "B", "database", "data", r"\bb\b"),
        "c": CatalogHit("c", "C", "cache", "data", r"\bc\b"),
    }
    for hit in hits.values():
        hit.evidence.append("a talks to b and c.")
    trace = TraceLog()
    default = RuleBasedConnectionLinker()
    custom = RuleBasedConnectionLinker(rules=(FirstTwoOnly(), SourceToTarget()))
    sentences = ["a talks to b and c."]
    default_links, _ = default.link(sentences, hits, TraceLog())
    custom_links, _ = custom.link(sentences, hits, trace)
    assert {(c.source_id, c.target_id) for c in default_links} == {("a", "c")}
    assert {(c.source_id, c.target_id) for c in custom_links} == {("a", "b")}
    assert custom_links[0].rule == "first_two"
