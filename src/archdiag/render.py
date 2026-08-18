from __future__ import annotations

from collections import defaultdict

from archdiag.layout import (
    BOX_H,
    BOX_W,
    COL_W,
    KIND_STROKE,
    PAD_X,
    ZONE_TINT,
    edge_path,
    label_anchor,
    layout_boxes,
    wrap_lines,
)
from archdiag.schema import Component, Connection


def render_svg(
    components: list[Component],
    connections: list[Connection],
    ambiguities: list[str],
) -> str:
    cols, boxes, width, diagram_bottom = layout_boxes(components)
    amb = ambiguities or ["None flagged."]
    amb_lines: list[str] = []
    for item in amb:
        amb_lines.extend(wrap_lines(item, 96))
    height = diagram_bottom + 36 + 18 * (len(amb_lines) + 1)
    fan = _fan_offsets(connections)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        _defs(),
        "<style>"
        "text{font-family:Segoe UI,sans-serif;font-size:12px;fill:#1d2430}"
        ".muted{fill:#5c6777;font-size:11px}.title{font-size:16px;font-weight:700}"
        ".zone{font-size:11px;font-weight:700;letter-spacing:.06em}"
        ".node:hover rect{filter:brightness(0.98)}"
        "</style>",
        '<rect width="100%" height="100%" fill="#f7f5f0"/>',
        '<text class="title" x="24" y="28">Architecture from technical notes</text>',
        '<text class="muted" x="24" y="44">Boxes and arrows are evidenced in the notes — nothing extra is invented</text>',
    ]

    for i, zone in enumerate(cols):
        x = PAD_X + i * COL_W - 10
        zone_boxes = [
            box
            for box in boxes.values()
            if (box.component.zone if box.component.zone in ZONE_TINT else "unspecified") == zone
        ]
        bottom = max((box.y + BOX_H for box in zone_boxes), default=120)
        col_h = max(bottom - 42, 88)
        tint = ZONE_TINT.get(zone, "#f1f3f5")
        parts.append(
            f'<rect x="{x}" y="54" width="{COL_W - 16}" height="{col_h:.0f}" rx="12" fill="{tint}" stroke="#e6dfd4"/>'
        )
        parts.append(f'<text class="zone muted" x="{x + 14}" y="74">{_xml(zone.upper())}</text>')

    for conn in connections:
        src = boxes.get(conn.source_id)
        dst = boxes.get(conn.target_id)
        if src is None or dst is None:
            continue
        offset = fan[(conn.source_id, conn.target_id)]
        path = edge_path(src, dst, offset)
        lx, ly = label_anchor(src, dst, offset)
        parts.append(
            f'<g class="edge" data-source="{_xml(conn.source_id)}" data-target="{_xml(conn.target_id)}">'
            f"<title>{_xml(conn.source_id)} → {_xml(conn.target_id)} [{_xml(conn.rule)}] {_xml(conn.evidence[:160])}</title>"
            f'<path d="{path}" fill="none" stroke="#3d4a5c" stroke-width="1.7" marker-end="url(#arrow)"/>'
        )
        if conn.label and conn.label != "described flow":
            parts.append(
                f'<text class="muted" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{_xml(conn.label)}</text>'
            )
        parts.append("</g>")

    for box in boxes.values():
        comp = box.component
        stroke = KIND_STROKE.get(comp.kind, "#0f6e62")
        quote = (
            comp.evidence_spans[0].sentence
            if comp.evidence_spans
            else (comp.evidence[0] if comp.evidence else "")
        )
        subtitle = next((d for d in comp.details if not d.startswith("Matched:")), None) or comp.kind.replace(
            "_", " "
        )
        parts.append(
            f'<g class="node" data-id="{_xml(comp.id)}" tabindex="0">'
            f"<title>{_xml(comp.name)} — {_xml(quote[:180])}</title>"
            f'<rect x="{box.x}" y="{box.y}" width="{BOX_W}" height="{BOX_H}" rx="10" fill="#fffdf8" stroke="{stroke}" stroke-width="1.8"/>'
            f'<text x="{box.x + 12}" y="{box.y + 26}" font-weight="650">{_xml(comp.name[:30])}</text>'
            f'<text class="muted" x="{box.x + 12}" y="{box.y + 44}">{_xml(subtitle[:32])}</text></g>'
        )

    y = diagram_bottom + 18
    parts.append(f'<text class="muted" x="24" y="{y}">Ambiguous or insufficient information</text>')
    for i, line in enumerate(amb_lines):
        parts.append(f'<text class="muted" x="24" y="{y + 18 + i * 16}">{_xml("• " + line)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _fan_offsets(connections: list[Connection]) -> dict[tuple[str, str], float]:
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for conn in connections:
        buckets[conn.target_id].append((conn.source_id, conn.target_id))
    offsets: dict[tuple[str, str], float] = {}
    for edges in buckets.values():
        mid = (len(edges) - 1) / 2
        for i, key in enumerate(edges):
            offsets[key] = (i - mid) * 22
    return offsets


def _defs() -> str:
    return (
        "<defs><marker id='arrow' markerWidth='9' markerHeight='9' refX='8' refY='3' orient='auto'>"
        "<path d='M0,0 L8,3 L0,6 z' fill='#3d4a5c'/></marker></defs>"
    )


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
