from __future__ import annotations

from dataclasses import dataclass

from archdiag.schema import Component

ZONE_ORDER = ("external", "edge", "application", "data", "internal", "unspecified")
BOX_W, BOX_H = 196, 62
COL_W, ROW_H = 236, 102
PAD_X, PAD_Y = 28, 52

ZONE_TINT = {
    "external": "#eef3ff",
    "edge": "#fff4e6",
    "application": "#eaf8f4",
    "data": "#f3eefe",
    "internal": "#f4f1ea",
    "unspecified": "#f1f3f5",
}
KIND_STROKE = {
    "client": "#4c6ef5",
    "firewall": "#c92a2a",
    "load_balancer": "#d9480f",
    "gateway": "#d9480f",
    "proxy": "#d9480f",
    "application_server": "#0b7285",
    "application_service": "#0b7285",
    "api": "#0b7285",
    "database": "#5f3dc4",
    "cache": "#5f3dc4",
    "storage": "#5f3dc4",
    "queue": "#5f3dc4",
    "external_system": "#7048e8",
    "observability": "#7048e8",
    "network_zone": "#5c6777",
    "network": "#5c6777",
    "cdn": "#d9480f",
}


@dataclass(frozen=True)
class Box:
    component: Component
    x: float
    y: float

    @property
    def cx(self) -> float:
        return self.x + BOX_W / 2

    @property
    def cy(self) -> float:
        return self.y + BOX_H / 2


def group_by_zone(components: list[Component]) -> dict[str, list[Component]]:
    grouped: dict[str, list[Component]] = {z: [] for z in ZONE_ORDER}
    for comp in components:
        zone = comp.zone if comp.zone in grouped else "unspecified"
        grouped[zone].append(comp)
    return grouped


def layout_boxes(components: list[Component]) -> tuple[list[str], dict[str, Box], float, float]:
    grouped = group_by_zone(components)
    cols = [z for z in ZONE_ORDER if grouped[z]]
    boxes: dict[str, Box] = {}
    for i, zone in enumerate(cols):
        for j, comp in enumerate(grouped[zone]):
            boxes[comp.id] = Box(comp, PAD_X + i * COL_W, PAD_Y + 28 + j * ROW_H)
    max_rows = max((len(grouped[z]) for z in cols), default=1)
    width = max(PAD_X * 2 + max(len(cols), 1) * COL_W, 820)
    diagram_bottom = PAD_Y + 28 + max_rows * ROW_H
    return cols, boxes, width, diagram_bottom


def border_point(box: Box, toward_x: float, toward_y: float) -> tuple[float, float]:
    dx = toward_x - box.cx
    dy = toward_y - box.cy
    if dx == 0 and dy == 0:
        return box.cx, box.cy
    tx = (BOX_W / 2) / abs(dx) if dx else 1e9
    ty = (BOX_H / 2) / abs(dy) if dy else 1e9
    scale = min(tx, ty)
    return box.cx + dx * scale, box.cy + dy * scale


def edge_path(src: Box, dst: Box, offset: float) -> str:
    x1, y1 = border_point(src, dst.cx, dst.cy)
    x2, y2 = border_point(dst, src.cx, src.cy)
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    # Perpendicular nudge so parallel flows (LB→apps and monitoring→apps) do not overlap.
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    nx, ny = -dy / length, dx / length
    cx = mx + nx * (28 + offset)
    cy = my + ny * (28 + offset)
    return f"M {x1:.1f},{y1:.1f} Q {cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"


def label_anchor(src: Box, dst: Box, offset: float) -> tuple[float, float]:
    x1, y1 = src.cx, src.cy
    x2, y2 = dst.cx, dst.cy
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    nx, ny = -dy / length, dx / length
    return (x1 + x2) / 2 + nx * (12 + offset * 0.4), (y1 + y2) / 2 + ny * (12 + offset * 0.4) - 6


def wrap_lines(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:width]]
