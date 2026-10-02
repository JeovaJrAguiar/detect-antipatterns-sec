import socket

import pytest

from observa.security.ssrf_guard import validate_remote_url


def test_validate_remote_url_rejects_http(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 0, 0, "", (("93.184.216.34", 443)))]
    )

    with pytest.raises(ValueError, match="HTTPS"):
        validate_remote_url("http://example.com")


def test_validate_remote_url_rejects_private_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 0, 0, "", (("127.0.0.1", 443)))]
    )

    with pytest.raises(ValueError, match="private|loopback|link-local|metadata"):
        validate_remote_url("https://localhost")


def test_validate_remote_url_respects_allowlist(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 0, 0, "", (("93.184.216.34", 443)))]
    )
    monkeypatch.setenv("OBSERVA_ALLOWED_REMOTE_HOSTS", "example.com")

    url = validate_remote_url("https://example.com")
    assert url.startswith("https://example.com")

    with pytest.raises(ValueError, match="allowlist"):
        validate_remote_url("https://evil.example")
