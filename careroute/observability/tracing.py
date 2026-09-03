"""OpenTelemetry Distributed Tracing configuration for CareRoute.

Provides span instrumentation for end-to-end tracing across multi-agent handoffs,
tool calls, knowledge graph lookups, and human-in-the-loop interactions.
Initializes the TracerProvider with CloudTraceSpanExporter for Google Cloud Trace.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any, Dict, Generator, Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    
    # Initialize the exporter for Google Cloud Trace (Agent Platform)
    provider = TracerProvider()
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if project_id and project_id not in ("default-project-id", "None"):
        cloud_trace_exporter = CloudTraceSpanExporter(project_id=project_id)
        provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
    trace.set_tracer_provider(provider)
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class TracerManager:
    """Manages OpenTelemetry tracer lifecycle via ADK global setup."""

    def __init__(self, service_name: str = "careroute-agent"):
        self.service_name = service_name
        self._tracer = trace.get_tracer(self.service_name) if OTEL_AVAILABLE else None

    @contextlib.contextmanager
    def span(
        self,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[Any, None, None]:
        """Creates a contextual OpenTelemetry trace span with custom metadata."""
        if not OTEL_AVAILABLE or not self._tracer:
            class MockSpan:
                def set_attribute(self, key: str, value: Any) -> None:
                    pass
                def set_status(self, *args: Any, **kwargs: Any) -> None:
                    pass
                def record_exception(self, exc: Exception) -> None:
                    pass
            yield MockSpan()
            return

        with self._tracer.start_as_current_span(span_name) as current_span:
            if attributes:
                for k, v in attributes.items():
                    if isinstance(v, (bool, str, bytes, int, float)):
                        current_span.set_attribute(k, v)
                    else:
                        current_span.set_attribute(k, str(v))
            yield current_span


# Global tracer singleton
tracer = TracerManager()
