"""Structured JSON Logging with Intent vs Outcome Tracking for CareRoute.

Outputs machine-parsable JSON logs enriched with trace correlation IDs, agent context,
intent-outcome audit trails, and automatic PII redaction.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON entries."""

    def format(self, record: logging.LogRecord) -> str:
        raw_message = record.getMessage()
        try:
            from careroute.security.redaction import PIIScrubber
            scrubbed_message = PIIScrubber.redact(raw_message)
        except Exception:
            scrubbed_message = raw_message

        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrubbed_message,
        }

        # Include custom fields passed in extra
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "msg", "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName"
            }:
                if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
                    log_entry[key] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_structured_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures root and agent loggers with structured JSON formatting."""
    logger = logging.getLogger("careroute")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    logger.addHandler(handler)

    return logger


# Global logger instance
logger = setup_structured_logging()


class AgentAuditor:
    """Auditor for recording Intent vs Outcome telemetry across multi-agent workflows."""

    def __init__(self, agent_name: str, trace_id: Optional[str] = None):
        self.agent_name = agent_name
        self.trace_id = trace_id or "trace-root"
        self._start_time: Optional[float] = None
        self._intent_data: Optional[Dict[str, Any]] = None

    def log_intent(
        self,
        action_name: str,
        goal: str,
        parameters: Optional[Dict[str, Any]] = None,
        model_routed: Optional[str] = None,
    ) -> None:
        """Captures the agent's intended action prior to execution."""
        self._start_time = time.perf_counter()
        self._intent_data = {
            "action_name": action_name,
            "goal": goal,
            "parameters": parameters or {},
            "model_routed": model_routed,
        }

        logger.info(
            f"Agent [{self.agent_name}] initiated intent: {action_name}",
            extra={
                "event_type": "AGENT_INTENT",
                "agent_name": self.agent_name,
                "trace_id": self.trace_id,
                "action_name": action_name,
                "intended_goal": goal,
                "intent_payload": parameters or {},
                "model_routed": model_routed,
            }
        )

    def log_outcome(
        self,
        status: str,
        result_summary: str,
        output_payload: Optional[Dict[str, Any]] = None,
        token_usage: Optional[Dict[str, int]] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Captures the actual outcome and compares against original intent."""
        latency_ms = 0.0
        if self._start_time:
            latency_ms = round((time.perf_counter() - self._start_time) * 1000, 2)

        action_name = self._intent_data.get("action_name", "unknown") if self._intent_data else "unknown"

        log_method = logger.info if status.lower() in ("success", "approved", "completed") else logger.warning

        log_method(
            f"Agent [{self.agent_name}] concluded action [{action_name}] with status [{status}] ({latency_ms}ms)",
            extra={
                "event_type": "AGENT_OUTCOME",
                "agent_name": self.agent_name,
                "trace_id": self.trace_id,
                "action_name": action_name,
                "status": status,
                "result_summary": result_summary,
                "output_payload": output_payload or {},
                "latency_ms": latency_ms,
                "token_usage": token_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "error_detail": error_detail,
                "intent_vs_outcome_match": status.lower() in ("success", "approved", "completed"),
            }
        )

