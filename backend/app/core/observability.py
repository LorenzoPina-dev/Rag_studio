"""Observability foundations (OpenTelemetry hooks, structured-ready setup)."""

from __future__ import annotations

from app.core.config import settings


def setup_observability(app=None) -> None:
    """Configure tracing/metrics hooks when enabled.

    Designed to be safe in environments where optional exporters/instrumentation
    packages are not installed; failures are non-fatal.
    """
    if not getattr(settings, "otel_enabled", False):
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create(
            {
                "service.name": getattr(settings, "otel_service_name", "rag-studio-backend"),
                "deployment.environment": getattr(settings, "app_env", "development"),
            }
        )
        provider = TracerProvider(resource=resource)

        exporter = None
        endpoint = getattr(settings, "otel_exporter_otlp_endpoint", None)
        if endpoint:
            # Try common OTLP exporters; fall back to console if unavailable.
            for mod_name, cls_name in (
                ("opentelemetry.exporter.otlp.proto.grpc.trace_exporter", "OTLPSpanExporter"),
                ("opentelemetry.exporter.otlp.proto.http.trace_exporter", "OTLPSpanExporter"),
            ):
                try:
                    mod = __import__(mod_name, fromlist=[cls_name])
                    exporter_cls = getattr(mod, cls_name)
                    exporter = exporter_cls(endpoint=endpoint)
                    break
                except Exception:
                    exporter = None
        if exporter is None:
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        if app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
            except Exception:
                pass
    except Exception:
        # Observability must not prevent application startup
        return
