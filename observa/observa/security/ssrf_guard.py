import ipaddress
import os
import socket
from typing import Optional, Set
from urllib.parse import urlparse


def _allowed_hosts() -> Set[str]:
    raw = os.getenv("OBSERVA_ALLOWED_REMOTE_HOSTS", "")
    return {entry.strip().lower().rstrip(".") for entry in raw.split(",") if entry.strip()}


def _is_private_or_local_address(ip_value: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_value)
    except ValueError:
        return True

    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_remote_url(raw_url: str, *, allowed_hosts: Optional[Set[str]] = None) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Remote URL is required.")

    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("Remote endpoints must use HTTPS only.")

    host = parsed.hostname
    if not host:
        raise ValueError("Remote URL must include a valid hostname.")

    normalized_host = host.lower().rstrip(".")
    if normalized_host in {"localhost", "127.0.0.1", "0.0.0.0"} or normalized_host.endswith(".local"):
        raise ValueError("Remote URL points to a private, loopback, or local network address.")

    try:
        socket_info = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Remote URL hostname could not be resolved: {host}") from exc

    resolved_ips = {info[4][0] for info in socket_info if info[4] and len(info[4]) >= 2}
    if not resolved_ips:
        raise ValueError(f"Remote URL did not resolve to any reachable IP address: {host}")

    for ip_text in resolved_ips:
        if _is_private_or_local_address(ip_text):
            raise ValueError(
                f"Remote URL resolves to a private, loopback, link-local, or metadata address: {host} -> {ip_text}"
            )

    allowed = set((allowed_hosts or _allowed_hosts()))
    if allowed:
        host_allowed = any(
            normalized_host == candidate or normalized_host.endswith(f".{candidate}")
            for candidate in allowed
        )
        if not host_allowed:
            raise ValueError(
                f"Remote URL host '{host}' is not in the configured allowlist. "
                "Set OBSERVA_ALLOWED_REMOTE_HOSTS to permit this host."
            )

    return raw_url.strip()
