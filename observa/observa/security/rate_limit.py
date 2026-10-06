import json
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple
from urllib.parse import urlsplit

from fastapi import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window_seconds: int


_PERIODS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}
_MAX_BUCKETS = 10000


def parse_rate_limit(value: str) -> RateLimitPolicy:
    try:
        count_text, period = value.strip().lower().split("/", 1)
        count = int(count_text)
        window_seconds = _PERIODS[period]
    except (KeyError, ValueError) as error:
        raise ValueError("Rate limits must use '<positive integer>/<second|minute|hour|day>'.") from error

    if count < 1:
        raise ValueError("Rate limit count must be greater than zero.")
    return RateLimitPolicy(limit=count, window_seconds=window_seconds)


def configured_rate_limit(name: str) -> RateLimitPolicy:
    is_development = os.getenv("APP_ENV", "production").lower() == "development"
    defaults = {
        "LOGIN": "30/minute" if is_development else "5/minute",
        "USER_CREATE": "60/hour" if is_development else "5/hour",
        "RUN": "120/minute" if is_development else "20/minute",
        "REMOTE": "120/minute" if is_development else "30/minute",
    }
    if name not in defaults:
        raise ValueError(f"Unknown rate limit policy: {name}")
    return parse_rate_limit(os.getenv(f"OBSERVA_RATE_LIMIT_{name}", defaults[name]))


class InProcessRateLimiter:
    def __init__(self):
        self._windows: Dict[str, Tuple[Deque[float], int]] = {}
        self._lock = threading.Lock()
        self._checks = 0

    def consume(self, key: str, policy: RateLimitPolicy) -> Optional[int]:
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            if self._checks % 256 == 0:
                self._remove_expired_windows(now)

            bucket_key = key
            if bucket_key not in self._windows and len(self._windows) >= _MAX_BUCKETS:
                category = key.split(":", 1)[0]
                bucket_key = f"{category}:overflow"

            events, window_seconds = self._windows.get(
                bucket_key, (deque(), policy.window_seconds)
            )
            if window_seconds != policy.window_seconds:
                events = deque()
            cutoff = now - policy.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= policy.limit:
                return max(1, math.ceil(events[0] + policy.window_seconds - now))

            events.append(now)
            self._windows[bucket_key] = (events, policy.window_seconds)
            return None

    def _remove_expired_windows(self, now: float) -> None:
        for key, (events, window_seconds) in list(self._windows.items()):
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if not events:
                del self._windows[key]


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.limiter = InProcessRateLimiter()
        self.policies = {
            "LOGIN": configured_rate_limit("LOGIN"),
            "USER_CREATE": configured_rate_limit("USER_CREATE"),
            "RUN": configured_rate_limit("RUN"),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        policy_name = self._policy_for(scope)
        if policy_name is None:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        retry_after = self.limiter.consume(
            f"{policy_name}:{client_ip}", self.policies[policy_name]
        )
        if retry_after is None:
            await self.app(scope, receive, send)
            return

        body = json.dumps({"detail": "Rate limit exceeded"}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"retry-after", str(retry_after).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": 429, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def _policy_for(scope: Scope) -> Optional[str]:
        if scope.get("method") != "POST":
            return None

        path = scope.get("path", "")
        if path == "/api/v1/admin/login":
            return "LOGIN"
        if path == "/api/v1/admin/users":
            return "USER_CREATE"
        if path in {
            "/api/v1/runs/execute",
            "/api/v1/runs/autorun",
            "/api/v1/runs/collect",
        }:
            return "RUN"
        return None


_remote_limiter = InProcessRateLimiter()


def enforce_remote_rate_limit(url: str) -> None:
    hostname = urlsplit(url).hostname
    if not hostname:
        raise ValueError("Remote URL must include a hostname.")

    retry_after = _remote_limiter.consume(
        f"REMOTE:{hostname.lower()}", configured_rate_limit("REMOTE")
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Remote destination rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )