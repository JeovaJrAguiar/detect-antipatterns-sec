import asyncio
import json
import logging
import uuid

from fastapi import FastAPI

from observa.framework.orchestrator import Orchestrator
from observa.sources.data_source import DataSource
from observa.security.observability import (
    RequestLoggingMiddleware,
    StructuredJsonFormatter,
    trace_id_context,
)


def test_request_logging_generates_server_trace_id_and_logs_validated_user_id(caplog):
    client_trace_id = "97a66355-b385-4fa6-9a0d-73f3249cb28e"

    async def exercise_request():
        async def downstream_app(scope, receive, send):
            scope["state"]["user_id"] = 42
            orchestrator = Orchestrator()
            orchestrator.telemetry_masker = type(
                "PassThroughMasker", (), {"process": staticmethod(lambda data: data)}
            )()
            detector = type(
                "FakeDetector",
                (),
                {
                    "nameAP": "ap",
                    "name": "detector",
                    "detect": lambda self, data: {"count": len(data)},
                },
            )()
            orchestrator.run(
                detector=detector,
                source=DataSource(name="source", json_data=[{}]),
            )
            await send({"type": "http.response.start", "status": 201, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        middleware = RequestLoggingMiddleware(downstream_app)
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users/me",
            "query_string": b"token=must-not-be-logged",
            "client": ("127.0.0.1", 12345),
            "headers": [
                (b"x-trace-id", client_trace_id.encode("ascii")),
                (b"x-request-id", client_trace_id.encode("ascii")),
            ],
        }
        await middleware(scope, receive, send)
        return messages, scope

    with caplog.at_level(logging.INFO):
        messages, scope = asyncio.run(exercise_request())

    response_headers = dict(messages[0]["headers"])
    request_id = response_headers[b"x-request-id"].decode("ascii")
    trace_id = response_headers[b"x-trace-id"].decode("ascii")
    assert request_id == trace_id
    assert trace_id != client_trace_id
    assert str(uuid.UUID(request_id)) == request_id
    assert scope["state"]["trace_id"] == trace_id
    assert scope["state"]["request_id"] == trace_id

    record = next(record for record in caplog.records if record.name == "observa.request")
    assert record.trace_id == trace_id
    assert record.request_id == request_id
    assert record.user_id == 42
    assert record.status_code == 201
    assert record.path == "/api/v1/users/me"

    structured = json.loads(StructuredJsonFormatter().format(record))
    assert structured["event"] == "http_request"
    assert structured["trace_id"] == trace_id
    assert structured["request_id"] == request_id
    assert structured["user_id"] == 42
    assert "must-not-be-logged" not in json.dumps(structured)

    span_records = [record for record in caplog.records if record.name == "observa.trace"]
    started_spans = {
        record.span_name: record
        for record in span_records
        if record.getMessage() == "trace_span_started"
    }
    assert started_spans["analysis.run"].trace_id == trace_id
    assert started_spans["source.load"].trace_id == trace_id
    assert started_spans["detector.detect"].trace_id == trace_id
    assert started_spans["source.load"].parent_span_id == started_spans["analysis.run"].span_id
    assert started_spans["detector.detect"].parent_span_id == started_spans["analysis.run"].span_id


def test_request_logging_replaces_invalid_correlation_id():
    async def exercise_request():
        async def downstream_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = RequestLoggingMiddleware(downstream_app)
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "client": None,
            "headers": [(b"x-request-id", b"bad\r\nvalue")],
        }
        await middleware(scope, receive, send)
        return dict(messages[0]["headers"])[b"x-request-id"].decode("ascii")

    generated_id = asyncio.run(exercise_request())
    assert str(uuid.UUID(generated_id)) == generated_id


def test_trace_id_is_included_on_unhandled_server_error(caplog):
    client_trace_id = "b239a658-a74c-41f4-96f1-c7c4f33c6fd1"

    async def exercise_request():
        fastapi_app = FastAPI()

        @fastapi_app.get("/failure")
        async def failure():
            raise RuntimeError("sensitive exception detail")

        app = RequestLoggingMiddleware(fastapi_app)
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/failure",
            "raw_path": b"/failure",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"x-trace-id", client_trace_id.encode("ascii"))],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        try:
            await app(scope, receive, send)
        except RuntimeError:
            pass
        return messages

    with caplog.at_level(logging.INFO):
        messages = asyncio.run(exercise_request())

    assert messages[0]["status"] == 500
    response_headers = dict(messages[0]["headers"])
    response_trace_id = response_headers[b"x-trace-id"].decode("ascii")
    assert response_trace_id != client_trace_id
    assert str(uuid.UUID(response_trace_id)) == response_trace_id
    record = next(record for record in caplog.records if record.name == "observa.request")
    assert record.status_code == 500
    assert record.error_type == "RuntimeError"
    assert record.trace_id == response_trace_id
    assert record.request_id == response_trace_id
    assert "sensitive exception detail" not in record.getMessage()


def test_remote_calls_forward_server_trace_id(monkeypatch):
    from observa.detectors import remote_detector
    from observa.sources import remote_source

    calls = []

    class Response:
        status_code = 200
        is_redirect = False

        @staticmethod
        def json():
            return {}

    class Session:
        def get(self, url, **kwargs):
            calls.append(kwargs)
            return Response()

        def post(self, url, **kwargs):
            calls.append(kwargs)
            return Response()

    monkeypatch.setattr(remote_source, "validate_remote_url", lambda url: url)
    monkeypatch.setattr(remote_detector, "validate_remote_url", lambda url: url)
    monkeypatch.setattr(remote_source, "enforce_remote_rate_limit", lambda url: None)
    monkeypatch.setattr(remote_detector, "enforce_remote_rate_limit", lambda url: None)
    monkeypatch.setattr(remote_source.requests, "Session", Session)

    trace_id = "7a909d82-3fd5-4435-9d32-ec5d6ccf7f04"
    context_token = trace_id_context.set(trace_id)
    try:
        remote_source.RemoteSource(name="source", api_url="https://source.example").load()
        remote_detector.RemoteDetector(
            name="detector",
            nameAP="ap",
            api_url="https://detector.example",
        ).detect({})
    finally:
        trace_id_context.reset(context_token)

    assert len(calls) == 2
    for call in calls:
        assert call["headers"] == {
            "X-Trace-ID": trace_id,
            "X-Request-ID": trace_id,
        }