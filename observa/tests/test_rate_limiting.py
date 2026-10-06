import asyncio

from fastapi import HTTPException
import pytest

from observa.security import rate_limit
from observa.security.rate_limit import (
    InProcessRateLimiter,
    RateLimitMiddleware,
    enforce_remote_rate_limit,
)


@pytest.mark.parametrize(
    ("path", "setting"),
    [
        ("/api/v1/admin/login", "OBSERVA_RATE_LIMIT_LOGIN"),
        ("/api/v1/admin/users", "OBSERVA_RATE_LIMIT_USER_CREATE"),
        ("/api/v1/runs/execute", "OBSERVA_RATE_LIMIT_RUN"),
    ],
)
def test_http_rate_limit_returns_429_after_configured_request_count(
    monkeypatch, path, setting
):
    monkeypatch.setenv(setting, "1/minute")

    async def exercise_requests():
        async def downstream_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        middleware = RateLimitMiddleware(downstream_app)
        results = []

        async def send_request():
            messages = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            scope = {
                "type": "http",
                "method": "POST",
                "path": path,
                "client": ("127.0.0.1", 12345),
                "headers": [],
            }
            await middleware(scope, receive, send)
            results.append(messages)

        await send_request()
        await send_request()
        return results

    results = asyncio.run(exercise_requests())
    assert results[0][0]["status"] == 200
    assert results[1][0]["status"] == 429
    assert int(dict(results[1][0]["headers"])[b"retry-after"]) > 0


def test_remote_rate_limit_is_scoped_to_destination_host(monkeypatch):
    monkeypatch.setenv("OBSERVA_RATE_LIMIT_REMOTE", "1/minute")
    monkeypatch.setattr(rate_limit, "_remote_limiter", InProcessRateLimiter())

    enforce_remote_rate_limit("https://service.example/data")
    enforce_remote_rate_limit("https://other.example/data")

    try:
        enforce_remote_rate_limit("https://service.example/other")
    except HTTPException as error:
        assert error.status_code == 429
    else:
        raise AssertionError("Expected the second call to the same host to be limited")