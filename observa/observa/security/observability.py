import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

from starlette.types import ASGIApp, Message, Receive, Scope, Send


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_STRUCTURED_FIELDS = (
    "request_id",
    "user_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_type",
    "source_count",
    "detector_count",
)


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
        if "request_id" not in payload:
            payload["request_id"] = request_id_context.get()
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


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

        request_id = self._request_id(scope)
        request_context_token = request_id_context.set(request_id)
        request_state = scope.setdefault("state", {})
        started_at = time.perf_counter()
        status_code = 500
        error_type = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            log_fields = {
                "request_id": request_id,
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
            request_id_context.reset(request_context_token)

    @staticmethod
    def _request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                try:
                    return str(uuid.UUID(value.decode("ascii")))
                except (UnicodeDecodeError, ValueError):
                    break
        return str(uuid.uuid4())