from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archdiag.schema import ArchitectureDiagram

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvalCase:
    id: str
    notes_path: str
    required_components: frozenset[str]
    forbidden_components: frozenset[str]
    required_edges: frozenset[tuple[str, str]]
    min_ambiguities: int = 0


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="exercise_example",
        notes_path="sample_notes/exercise_example.txt",
        required_components=frozenset(
            {
                "external-users",
                "firewall",
                "load-balancer",
                "app-servers",
                "postgres",
                "auth-service",
                "monitoring",
                "internal-network",
            }
        ),
        forbidden_components=frozenset({"cache", "vpn", "cdn", "message-queue"}),
        required_edges=frozenset(
            {
                ("external-users", "firewall"),
                ("firewall", "load-balancer"),
                ("load-balancer", "app-servers"),
                ("app-servers", "postgres"),
                ("app-servers", "auth-service"),
                ("monitoring", "app-servers"),
                ("internal-network", "app-servers"),
            }
        ),
        min_ambiguities=3,
    ),
    EvalCase(
        id="api_gateway_cache",
        notes_path="sample_notes/api_gateway_cache.txt",
        required_components=frozenset({"api-gateway", "cache", "mysql", "app-servers"}),
        forbidden_components=frozenset({"firewall", "vpn"}),
        required_edges=frozenset({("api-gateway", "app-servers"), ("app-servers", "mysql")}),
    ),
)


@dataclass
class EvalScore:
    case_id: str
    recall: float
    missing: list[str]
    invented_forbidden: list[str]
    missing_edges: list[tuple[str, str]]
    ambiguity_ok: bool

    @property
    def passed(self) -> bool:
        return (
            self.recall == 1.0
            and not self.invented_forbidden
            and not self.missing_edges
            and self.ambiguity_ok
        )


def score_diagram(model: ArchitectureDiagram, case: EvalCase) -> EvalScore:
    ids = {c.id for c in model.components}
    edges = {(c.source_id, c.target_id) for c in model.connections}
    missing = sorted(case.required_components - ids)
    invented = sorted(case.forbidden_components & ids)
    missing_edges = sorted(case.required_edges - edges)
    recall = (
        (len(case.required_components) - len(missing)) / len(case.required_components)
        if case.required_components
        else 1.0
    )
    return EvalScore(
        case_id=case.id,
        recall=recall,
        missing=missing,
        invented_forbidden=invented,
        missing_edges=missing_edges,
        ambiguity_ok=len(model.ambiguities) >= case.min_ambiguities,
    )


def load_notes(case: EvalCase) -> str:
    return (ROOT / case.notes_path).read_text(encoding="utf-8")
