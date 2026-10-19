"""OpenInference instrumentation exported to Phoenix over OTLP/HTTP."""

from collections.abc import Generator
from contextlib import contextmanager

from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.configs.trace.trace_config import TraceConfig


@contextmanager
def tracing(config: TraceConfig) -> Generator[None]:
    """Instrument LangChain/LangGraph and flush queued spans on every exit path."""
    if not config.enabled:
        yield
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": config.service_name,
                "openinference.project.name": config.project_name,
            }
        )
    )
    instrumentor = LangChainInstrumentor()
    try:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=str(config.endpoint),
                    timeout=config.export_timeout_seconds,
                )
            )
        )
        instrumentor.instrument(tracer_provider=provider)
        yield
    finally:
        try:
            instrumentor.uninstrument()
        finally:
            provider.shutdown()
