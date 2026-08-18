"""Optional OpenTelemetry tracing (Datadog-compatible via OTLP).

No collector is required. If ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset or the
OpenTelemetry packages are missing, spans are no-ops.

Closest open-source Datadog-style backends that speak OTLP:
SigNoz, Grafana Tempo (LGTM stack), Jaeger, Uptrace.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator


def init_telemetry() -> str:
    """Configure an OTLP HTTP exporter when an endpoint is provided.

    Returns a short status string for ``GET /health``.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return "disabled"

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return "packages_missing"

    service = os.getenv("OTEL_SERVICE_NAME", "architecture-diagram-generator")
    traces_url = endpoint if endpoint.rstrip("/").endswith("traces") else endpoint.rstrip("/") + "/v1/traces"
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_url)))
    trace.set_tracer_provider(provider)
    return "otlp"


def _tracer() -> Any:
    try:
        from opentelemetry import trace

        return trace.get_tracer("archdiag")
    except ImportError:
        return None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    tracer = _tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield
