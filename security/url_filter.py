"""URL filtering to prevent SSRF attacks."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Blocked IP ranges (private, loopback, link-local, metadata)
_BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/Azure metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.azure.com"}


def is_url_safe(url: str) -> tuple[bool, str]:
    """Check if a URL is safe to fetch. Returns (safe, reason)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"Blocked scheme: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return False, "No hostname"

    # Check blocked hostnames
    if hostname in _BLOCKED_HOSTS:
        return False, f"Blocked host: {hostname}"

    # Try to resolve as IP
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_RANGES:
            if addr in network:
                return False, f"Blocked private IP: {hostname}"
    except ValueError:
        pass  # Not an IP literal, hostname is fine

    # Block common metadata paths
    if "169.254" in hostname or "metadata" in hostname:
        return False, "Blocked metadata endpoint"

    return True, ""
