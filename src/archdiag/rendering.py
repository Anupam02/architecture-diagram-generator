from __future__ import annotations

from archdiag.render import render_svg
from archdiag.schema import Component, Connection


class SvgRenderer:
    def render(
        self,
        components: list[Component],
        connections: list[Connection],
        ambiguities: list[str],
    ) -> str:
        return render_svg(components, connections, ambiguities)
