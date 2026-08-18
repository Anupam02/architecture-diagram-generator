import json
from unittest.mock import MagicMock, patch

from archdiag.llm import (
    ConstrainedLlmMerger,
    OpenAiCompatibleProposer,
    StaticProposer,
    VerbatimSpanGate,
    parse_proposal_json,
)
from archdiag.models import TraceLog
from archdiag.pipeline import interpret_notes
from archdiag.ports import ProposedComponent

NOTES = (
    "Mobile clients reach an EKS cluster through an API gateway. "
    "The API gateway forwards traffic to application servers."
)


def test_verbatim_gate_accepts_only_contiguous_quotes() -> None:
    gate = VerbatimSpanGate()
    notes = "Traffic reaches an EKS cluster on the internal network."
    assert gate.locate("EKS cluster", notes) == "EKS cluster"
    assert gate.locate("eks cluster", notes) == "EKS cluster"
    assert gate.locate("EKS  cluster", notes) == "EKS cluster"
    assert gate.locate("Redis", notes) is None


def test_llm_proposal_accepted_when_phrase_is_in_notes() -> None:
    proposer = StaticProposer(
        [ProposedComponent("EKS cluster", "EKS cluster", "application_server", "application")]
    )
    model = interpret_notes(NOTES, proposer=proposer)
    ids = {c.id for c in model.components}
    assert "eks-cluster" in ids
    assert "api-gateway" in ids
    assert model.llm_accepted == 1
    assert any(e.action == "llm_accepted" for e in model.extraction_trace)
    eks = next(c for c in model.components if c.id == "eks-cluster")
    assert eks.evidence_spans[0].rule == "llm:verbatim"
    assert "eks cluster" in eks.evidence_spans[0].sentence.lower()


def test_llm_proposal_rejected_when_invented() -> None:
    proposer = StaticProposer([ProposedComponent("Redis", "Redis", "cache", "data")])
    model = interpret_notes(NOTES, proposer=proposer)
    names = " ".join(c.name.lower() for c in model.components)
    assert "redis" not in names
    assert model.llm_rejected >= 1
    assert any(e.action == "llm_rejected" and e.rule == "verbatim_missing" for e in model.extraction_trace)


def test_llm_does_not_duplicate_catalog_hits() -> None:
    proposer = StaticProposer(
        [ProposedComponent("API gateway", "API gateway", "gateway", "edge")]
    )
    model = interpret_notes(NOTES, proposer=proposer)
    assert model.llm_accepted == 0
    assert any(e.rule == "already_catalogued" for e in model.extraction_trace)


def test_merger_records_reject_without_mutating_hits() -> None:
    hits: dict = {}
    trace = TraceLog()
    merger = ConstrainedLlmMerger()
    accepted, rejected = merger.merge(
        "only a firewall is mentioned here.",
        ["only a firewall is mentioned here."],
        hits,
        [ProposedComponent("Kafka", "Kafka")],
        trace,
    )
    assert accepted == 0
    assert rejected == 1
    assert hits == {}


def test_parse_proposal_json_strips_fences() -> None:
    raw = """```json
    {"components":[{"phrase":"EKS cluster","name":"EKS","kind":"application_server","zone":"application"}]}
    ```"""
    parsed = parse_proposal_json(raw)
    assert len(parsed) == 1
    assert parsed[0].phrase == "EKS cluster"


def test_openai_proposer_returns_empty_on_http_error() -> None:
    proposer = OpenAiCompatibleProposer("sk-test", "gpt-4o-mini", "https://api.openai.com/v1")
    with patch("archdiag.llm.urllib.request.urlopen", side_effect=TimeoutError):
        assert proposer.propose("notes about a firewall and a load balancer.", []) == []


def test_openai_proposer_parses_response_body() -> None:
    proposer = OpenAiCompatibleProposer("sk-test", "gpt-4o-mini", "https://example.test/v1")
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"components": [{"phrase": "EKS cluster", "name": "EKS", "kind": "application_server", "zone": "application"}]}
                    )
                }
            }
        ]
    }
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    with patch("archdiag.llm.urllib.request.urlopen", return_value=response):
        proposals = proposer.propose("see the EKS cluster please now.", [])
    assert proposals[0].phrase == "EKS cluster"
