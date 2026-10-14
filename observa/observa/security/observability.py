import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send


trace_id_context: ContextVar[str] = ContextVar("trace_id", default="-")
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
span_id_context: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_STRUCTURED_FIELDS = (
    "trace_id",
    "request_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "user_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_type",
    "source_count",
    "detector_count",
)
_logger = logging.getLogger("observa.trace")


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if "trace_id" not in payload:
            payload["trace_id"] = trace_id_context.get()
        if "request_id" not in payload:
            payload["request_id"] = request_id_context.get()
        if "span_id" not in payload:
            span_id = span_id_context.get()
            if span_id is not None:
                payload["span_id"] = span_id
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def trace_headers() -> Dict[str, str]:
    trace_id = trace_id_context.get()
    if trace_id == "-":
        return {}
    return {
        "X-Trace-ID": trace_id,
        "X-Request-ID": trace_id,
    }


@contextmanager
def trace_span(name: str) -> Iterator[None]:
    trace_id = trace_id_context.get()
    if trace_id == "-":
        yield
        return

    span_id = uuid.uuid4().hex[:16]
    parent_span_id = span_id_context.get()
    span_token = span_id_context.set(span_id)
    span_fields = {
        "trace_id": trace_id,
        "span_id": span_id,
        "span_name": name,
    }
    if parent_span_id is not None:
        span_fields["parent_span_id"] = parent_span_id

    started_at = time.perf_counter()
    _logger.info("trace_span_started", extra=span_fields)
    try:
        yield
    except Exception as error:
        _logger.info(
            "trace_span_failed",
            extra={
                **span_fields,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
                "error_type": type(error).__name__,
            },
        )
        raise
    else:
        _logger.info(
            "trace_span_finished",
            extra={
                **span_fields,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            },
        )
    finally:
        span_id_context.reset(span_token)


def configure_structured_logging() -> None:
    root_logger = logging.getLogger()
    level_name = os.getenv("OBSERVA_LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, level_name, logging.INFO))
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    for handler in root_logger.handlers:
        handler.setFormatter(StructuredJsonFormatter())


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.logger = logging.getLogger("observa.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = self._trace_id()
        root_span_id = uuid.uuid4().hex[:16]
        trace_context_token = trace_id_context.set(trace_id)
        request_context_token = request_id_context.set(trace_id)
        span_context_token = span_id_context.set(root_span_id)
        request_state = scope.setdefault("state", {})
        request_state["trace_id"] = trace_id
        request_state["request_id"] = trace_id
        started_at = time.perf_counter()
        status_code = 500
        error_type = None

        async def send_with_trace_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in {b"x-trace-id", b"x-request-id"}
                ]
                headers.append((b"x-trace-id", trace_id.encode("ascii")))
                headers.append((b"x-request-id", trace_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace_id)
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            log_fields = {
                "trace_id": trace_id,
                "request_id": trace_id,
                "span_id": root_span_id,
                "span_name": "http.request",
                "method": scope.get("method", "UNKNOWN"),
                "path": scope.get("path", ""),
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            }
            user_id = request_state.get("user_id")
            if isinstance(user_id, int) and not isinstance(user_id, bool):
                log_fields["user_id"] = user_id
            if error_type is not None:
                log_fields["error_type"] = error_type
            self.logger.info("http_request", extra=log_fields)
            span_id_context.reset(span_context_token)
            request_id_context.reset(request_context_token)
            trace_id_context.reset(trace_context_token)

    @staticmethod
    def _trace_id() -> str:
        return str(uuid.uuid4())