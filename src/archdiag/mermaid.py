from __future__ import annotations

from archdiag.layout import ZONE_ORDER, group_by_zone
from archdiag.schema import Component, Connection


def to_mermaid(components: list[Component], connections: list[Connection]) -> str:
    """Downloadable text diagram (Mermaid flowchart) using the same model as the SVG."""
    lines = ["flowchart LR"]
    grouped = group_by_zone(components)
    for zone in ZONE_ORDER:
        members = grouped.get(zone) or []
        if not members:
            continue
        lines.append(f"  subgraph {zone}[{zone}]")
        for comp in members:
            lines.append(f"    {comp.id}[{_escape(comp.name)}]")
        lines.append("  end")
    for conn in connections:
        label = conn.label if conn.label != "described flow" else conn.rule
        lines.append(f"  {conn.source_id} -->|{_escape(label)}| {conn.target_id}")
    return "\n".join(lines) + "\n"


def _escape(text: str) -> str:
    return text.replace('"', "'").replace("[", "(").replace("]", ")")
