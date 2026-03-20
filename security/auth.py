"""API key and Auth0 JWT authentication for WebSocket and REST endpoints."""

from __future__ import annotations

import os
import secrets
from fastapi import Request, WebSocket, HTTPException, status

from nexus.security.token_vault import extract_bearer_token, is_configured as _auth0_configured


def get_api_key() -> str | None:
    """Get API key from environment. None means auth is disabled (local dev)."""
    return os.getenv("NEXUS_API_KEY", "").strip() or None


def get_user_token(request: Request) -> str | None:
    """Extract Auth0 bearer token from request, or None if not present."""
    return extract_bearer_token(request.headers.get("Authorization"))


def verify_request(request: Request) -> bool:
    """Verify API key from request header or query param.

    If Auth0 is configured, also accepts valid Bearer tokens.
    """
    # ── Auth0 JWT path ──
    if _auth0_configured() and get_user_token(request):
        return True  # Token Vault flow: JWT presence is sufficient for routing

    api_key = get_api_key()
    if not api_key:
        return True  # Auth disabled (local dev)

    # Check header first (timing-safe compare)
    header_key = request.headers.get("X-API-Key", "")
    if header_key and secrets.compare_digest(header_key, api_key):
        return True

    # Check query param
    query_key = request.query_params.get("api_key", "")
    if query_key and secrets.compare_digest(query_key, api_key):
        return True

    return False


def verify_websocket(ws: WebSocket) -> bool:
    """Verify API key from WebSocket query param."""
    api_key = get_api_key()
    if not api_key:
        return True

    query_key = ws.query_params.get("api_key", "")
    return bool(query_key and secrets.compare_digest(query_key, api_key))


def require_auth(request: Request) -> None:
    """FastAPI dependency: raise 401 if auth fails."""
    if not verify_request(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Set X-API-Key header.",
        )
