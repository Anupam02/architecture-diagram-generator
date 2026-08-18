from pathlib import Path

from archdiag.evaluate import CASES, load_notes, score_diagram
from archdiag.mermaid import to_mermaid
from archdiag.pipeline import interpret_notes


def test_eval_cases_pass_catalog_extractor() -> None:
    for case in CASES:
        model = interpret_notes(load_notes(case))
        result = score_diagram(model, case)
        assert result.passed, (
            f"{case.id} failed recall={result.recall} missing={result.missing} "
            f"invented={result.invented_forbidden} edges={result.missing_edges}"
        )


def test_svg_uses_zone_bands_and_curved_edges() -> None:
    notes = Path("sample_notes/exercise_example.txt").read_text(encoding="utf-8")
    model = interpret_notes(notes)
    assert 'class="node"' in model.svg
    assert "<path d=" in model.svg
    assert "EXTERNAL" in model.svg
    assert "marker-end" in model.svg


def test_mermaid_export_contains_same_ids() -> None:
    notes = Path("sample_notes/exercise_example.txt").read_text(encoding="utf-8")
    model = interpret_notes(notes)
    text = model.mermaid or to_mermaid(model.components, model.connections)
    assert text.startswith("flowchart LR")
    assert "firewall" in text
    assert "postgres" in text
    assert "-->" in text
