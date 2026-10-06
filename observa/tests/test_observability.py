import asyncio
import json
import logging
import uuid

from fastapi import FastAPI

from observa.security.observability import (
    RequestLoggingMiddleware,
    StructuredJsonFormatter,
)


def test_request_logging_generates_server_id_and_logs_validated_user_id(caplog):
    client_request_id = "97a66355-b385-4fa6-9a0d-73f3249cb28e"

    async def exercise_request():
        async def downstream_app(scope, receive, send):
            scope["state"]["user_id"] = 42
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
            "headers": [(b"x-request-id", client_request_id.encode("ascii"))],
        }
        await middleware(scope, receive, send)
        return messages

    with caplog.at_level(logging.INFO, logger="observa.request"):
        messages = asyncio.run(exercise_request())

    response_headers = dict(messages[0]["headers"])
    request_id = response_headers[b"x-request-id"].decode("ascii")
    assert request_id != client_request_id
    assert str(uuid.UUID(request_id)) == request_id
    record = next(record for record in caplog.records if record.name == "observa.request")
    assert record.request_id == request_id
    assert record.user_id == 42
    assert record.status_code == 201
    assert record.path == "/api/v1/users/me"

    structured = json.loads(StructuredJsonFormatter().format(record))
    assert structured["event"] == "http_request"
    assert structured["request_id"] == request_id
    assert structured["user_id"] == 42
    assert structured["request_id"] == request_id
    assert "must-not-be-logged" not in json.dumps(structured)


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


def test_request_id_is_included_on_unhandled_server_error(caplog):
    request_id = "b239a658-a74c-41f4-96f1-c7c4f33c6fd1"

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
            "headers": [(b"x-request-id", request_id.encode("ascii"))],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        try:
            await app(scope, receive, send)
        except RuntimeError:
            pass
        return messages

    with caplog.at_level(logging.INFO, logger="observa.request"):
        messages = asyncio.run(exercise_request())

    assert messages[0]["status"] == 500
    response_request_id = dict(messages[0]["headers"])[b"x-request-id"].decode("ascii")
    assert response_request_id != request_id
    assert str(uuid.UUID(response_request_id)) == response_request_id
    record = next(record for record in caplog.records if record.name == "observa.request")
    assert record.status_code == 500
    assert record.error_type == "RuntimeError"
    assert record.request_id == response_request_id
    assert "sensitive exception detail" not in record.getMessage()