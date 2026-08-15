from __future__ import annotations

from archdiag.schema import Component, Connection


def render_svg(
    components: list[Component],
    connections: list[Connection],
    ambiguities: list[str],
) -> str:
    zone_order = ["external", "edge", "application", "data", "internal", "unspecified"]
    grouped: dict[str, list[Component]] = {z: [] for z in zone_order}
    for comp in components:
        if comp.zone in grouped:
            grouped[comp.zone].append(comp)
        else:
            grouped["unspecified"].append(comp)
    cols = [z for z in zone_order if grouped.get(z)]
    col_w, row_h, pad = 230, 96, 36
    width = max(pad * 2 + max(len(cols), 1) * col_w, 760)
    max_rows = max((len(grouped[z]) for z in cols), default=1)
    amb = ambiguities or ["None flagged."]
    height = pad * 2 + 70 + max_rows * row_h + 36 + 20 * len(amb)

    positions: dict[str, tuple[float, float]] = {}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs><marker id='arrow' markerWidth='8' markerHeight='8' refX='6' refY='3' orient='auto'><path d='M0,0 L6,3 L0,6 z' fill='#3d4a5c'/></marker></defs>",
        "<style>text{font-family:Segoe UI,sans-serif;font-size:12px;fill:#1d2430}.muted{fill:#5c6777;font-size:11px}.title{font-size:16px;font-weight:700}</style>",
        '<rect width="100%" height="100%" fill="#f4f1ea"/>',
        '<text class="title" x="24" y="28">Architecture from technical notes</text>',
    ]
    for i, zone in enumerate(cols):
        x = pad + i * col_w
        parts.append(f'<text class="muted" x="{x}" y="54">{_xml(zone.upper())}</text>')
        for j, comp in enumerate(grouped[zone]):
            cy = 68 + j * row_h
            positions[comp.id] = (x + 90, cy + 28)
            parts.append(
                f'<rect x="{x}" y="{cy}" width="190" height="58" rx="8" fill="#fffdf8" stroke="#0f6e62"/>'
            )
            parts.append(f'<text x="{x + 10}" y="{cy + 24}">{_xml(comp.name[:32])}</text>')
            subtitle = comp.details[0] if comp.details else comp.kind.replace("_", " ")
            parts.append(f'<text class="muted" x="{x + 10}" y="{cy + 42}">{_xml(subtitle[:34])}</text>')

    for conn in connections:
        if conn.source_id not in positions or conn.target_id not in positions:
            continue
        x1, y1 = positions[conn.source_id]
        x2, y2 = positions[conn.target_id]
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3d4a5c" stroke-width="1.6" marker-end="url(#arrow)"/>'
        )
        parts.append(
            f'<text class="muted" x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 8}">{_xml(conn.label)}</text>'
        )

    y = height - 16 - 20 * len(amb)
    parts.append(f'<text class="muted" x="24" y="{y}">Ambiguous or insufficient information</text>')
    for i, item in enumerate(amb):
        parts.append(f'<text class="muted" x="24" y="{y + 18 + i * 18}">{_xml("- " + item[:120])}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
