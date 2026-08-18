from archdiag.telemetry import init_telemetry, span


def test_telemetry_disabled_without_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert init_telemetry() == "disabled"
    with span("unit.test", notes_chars=3):
        pass
