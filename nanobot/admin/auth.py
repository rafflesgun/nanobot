"""Authentication helpers for the gateway admin API."""

from __future__ import annotations

import hmac
from collections.abc import Mapping


def bearer_token(headers: Mapping[str, str]) -> str | None:
    """Return the bearer token from headers, or None when absent/malformed."""
    auth = None
    for name, value in headers.items():
        if name.lower() == "authorization":
            auth = value
            break
    if not auth:
        return None
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token or None


def is_authorized(
    headers: Mapping[str, str],
    *,
    enabled: bool,
    configured_token: str,
) -> bool:
    """Validate admin access using a configured bearer token."""
    if not enabled:
        return False
    expected = configured_token.strip()
    if not expected:
        return False
    supplied = bearer_token(headers)
    if not supplied:
        return False
    return hmac.compare_digest(supplied, expected)
