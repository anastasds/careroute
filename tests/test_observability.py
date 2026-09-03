"""Unit tests for CareRoute Observability: Structured JSON Logging, and OpenTelemetry Tracing."""

import json
import logging
from io import StringIO
import pytest
from careroute.observability.logger import AgentAuditor, StructuredJSONFormatter, logger
from careroute.observability.tracing import tracer


def test_structured_json_logger_intent_vs_outcome():
    """Validates that structured logger records intent before and outcome after execution."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJSONFormatter())
    logger.addHandler(handler)

    try:
        auditor = AgentAuditor(agent_name="TestSafetyAgent", trace_id="trace-test-99")
        auditor.log_intent(
            action_name="screen_drugs",
            goal="Screen 2 drugs for safety",
            parameters={"drugs": ["Warfarin", "Ibuprofen"]},
            model_routed="gemini-2.5-pro"
        )
        auditor.log_outcome(
            status="success",
            result_summary="Screening complete. 1 interaction detected.",
            output_payload={"contraindications": 1}
        )

        log_output = stream.getvalue()
        lines = [line.strip() for line in log_output.strip().split("\n") if line.strip()]
        assert len(lines) >= 2

        intent_json = json.loads(lines[0])
        assert intent_json["event_type"] == "AGENT_INTENT"
        assert intent_json["agent_name"] == "TestSafetyAgent"
        assert intent_json["trace_id"] == "trace-test-99"

        outcome_json = json.loads(lines[1])
        assert outcome_json["event_type"] == "AGENT_OUTCOME"
        assert outcome_json["status"] == "success"
        assert outcome_json["intent_vs_outcome_match"] is True
    finally:
        logger.removeHandler(handler)


def test_opentelemetry_tracer_span_creation():
    """Validates OpenTelemetry span context lifecycle."""
    with tracer.span("TestSpan", {"test_attribute": "value_123"}) as span:
        assert span is not None

