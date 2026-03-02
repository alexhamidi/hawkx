"""
HTTP client for X's internal GraphQL API.
Handles auth headers shared across all functions.

Auth pattern:
  - Authorization: Bearer <static token>  — identifies the web client
  - x-csrf-token: <ct0 cookie value>      — CSRF, must match the ct0 cookie
  - x-twitter-auth-type: OAuth2Session    — signals an authenticated session
  - cookies: auth_token + ct0             — the user's session identity
"""

import requests
from .creds import get_cookies
from .constants import BEARER

_cookies = None


def _get_cookies() -> dict:
    global _cookies
    if _cookies is None:
        _cookies = get_cookies(".x.com")
    return _cookies


def gql_get(path: str, params: dict) -> dict:
    """
    Make an authenticated GET request to X's internal GraphQL API.

    Args:
        path:   GraphQL path in the form "<queryId>/<QueryName>"
        params: Query params (variables, features, fieldToggles as JSON strings)

    Returns:
        Parsed JSON response. Raises on non-2xx.
    """
    cookies = _get_cookies()
    resp = requests.get(
        f"https://x.com/i/api/graphql/{path}",
        params=params,
        headers={
            "authorization": f"Bearer {BEARER}",
            "x-csrf-token": cookies["ct0"],
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        },
        cookies=cookies,
    )
    resp.raise_for_status()
    return resp.json()
