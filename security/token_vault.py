"""Auth0 Token Vault — secure per-user API token retrieval for Nexus agents.

Token Vault lets Nexus agents call third-party APIs (GitHub, Google) on behalf
of the authenticated user, without storing long-lived credentials.

Flow:
  1. User logs in via Auth0  →  receives a short-lived JWT
  2. JWT is sent with each WebSocket / REST request
  3. Before calling an external API, the agent calls get_connection_token()
  4. Auth0 returns a scoped, short-lived connection token
  5. Agent uses that token — Nexus never sees the raw credentials

Required .env variables:
  AUTH0_DOMAIN         e.g.  dev-xxxx.us.auth0.com
  AUTH0_CLIENT_ID      From Auth0 Application settings
  AUTH0_CLIENT_SECRET  From Auth0 Application settings
  AUTH0_AUDIENCE       API identifier (e.g. https://nexus-ai/api)
  AUTH0_CALLBACK_URL   e.g. http://localhost:8000/auth/callback
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AUTH0_DOMAIN        = os.getenv("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID     = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "")
AUTH0_AUDIENCE      = os.getenv("AUTH0_AUDIENCE", "")
AUTH0_CALLBACK_URL  = os.getenv("AUTH0_CALLBACK_URL", "http://localhost:8000/auth/callback")

# Connections supported by Token Vault in this app
# key = Auth0 connection name, value = display name
CONNECTIONS: dict[str, str] = {
    "github":       "GitHub",
    "google-oauth2": "Google Calendar",
}


def is_configured() -> bool:
    """Return True if Auth0 credentials are set in environment."""
    return bool(AUTH0_DOMAIN and AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET)


def get_login_url(state: str = "") -> str:
    """Build the Auth0 authorization URL for user login."""
    params = {
        "response_type": "code",
        "client_id":     AUTH0_CLIENT_ID,
        "redirect_uri":  AUTH0_CALLBACK_URL,
        "scope":         "openid profile email offline_access",
        "audience":      AUTH0_AUDIENCE,
    }
    if state:
        params["state"] = state
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://{AUTH0_DOMAIN}/authorize?{query}"


async def exchange_code_for_tokens(code: str) -> dict | None:
    """Exchange OAuth authorization code for access + refresh tokens."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://{AUTH0_DOMAIN}/oauth/token",
                json={
                    "grant_type":    "authorization_code",
                    "client_id":     AUTH0_CLIENT_ID,
                    "client_secret": AUTH0_CLIENT_SECRET,
                    "code":          code,
                    "redirect_uri":  AUTH0_CALLBACK_URL,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Token exchange failed: HTTP %d — %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Token exchange error: %s", e)
        return None


async def get_connection_token(user_access_token: str, connection: str) -> str | None:
    """Exchange user's Auth0 JWT for a scoped connection token via Token Vault.

    Args:
        user_access_token: The user's Auth0 access token.
        connection: Auth0 connection name, e.g. "github" or "google-oauth2".

    Returns:
        A short-lived connection access token, or None if unavailable.
    """
    if not is_configured() or not user_access_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://{AUTH0_DOMAIN}/oauth/token",
                json={
                    "grant_type":           "urn:ietf:params:oauth:grant-type:token-exchange",
                    "subject_token":        user_access_token,
                    "subject_token_type":   "urn:ietf:params:oauth:token-type:access_token",
                    "requested_token_type": "urn:auth0:params:oauth:token-type:connection",
                    "connection":           connection,
                    "client_id":            AUTH0_CLIENT_ID,
                    "client_secret":        AUTH0_CLIENT_SECRET,
                },
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                logger.debug("Token Vault: got token for connection=%s", connection)
                return token
            # 400 = connection not linked by user; 401 = bad token — both are non-fatal
            logger.debug(
                "Token Vault: connection=%s not available (HTTP %d)",
                connection, resp.status_code,
            )
            return None
    except Exception as e:
        logger.warning("Token Vault error for %s: %s", connection, e)
        return None


async def get_user_connections(user_access_token: str) -> list[dict]:
    """Return connection status for all supported services.

    Returns a list like:
      [{"id": "github", "name": "GitHub", "connected": True}, ...]
    """
    results = []
    for conn_id, conn_name in CONNECTIONS.items():
        token = await get_connection_token(user_access_token, conn_id)
        results.append({
            "id":        conn_id,
            "name":      conn_name,
            "connected": token is not None,
        })
    return results


def extract_bearer_token(authorization: str | None) -> str | None:
    """Extract Bearer token from 'Authorization: Bearer <token>' header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    return token or None
