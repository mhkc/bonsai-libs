"""Manage API authentication."""

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol
from threading import RLock
import time
from .exceptions import UnauthorizedError


class AuthStrategy(Protocol):
    """Pluggable auth header provider."""

    def headers(self) -> Mapping[str, str]:
        """Return headers to attach to a API request."""

    def refresh(self) -> bool:
        """Refresh tokens proactively. Return True if changed."""

        return False

    def force_refresh(self) -> bool:
        """Force token refresh. Return True if changed."""


@dataclass
class BearerTokenAuth(AuthStrategy):
    """Static bearer token, no refresh."""

    token: str

    def headers(self) -> Mapping[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass
class OAuth2Token:
    """A runtime container for OAuth2 tokens."""

    access_token: str
    token_type: str = "Bearer"

    # Absolute expiry in seconds
    expires_at: float | None = None
    # refresh token if the provider issues one
    refresh_token: str | None = None

    @classmethod
    def from_expires_in(
        cls,
        access_token: str,
        expires_in: int,
        token_type: str = "Bearer",
        refresh_token: str | None = None,
        skew: int = 30,
    ) -> "OAuth2Token":
        """Refresh token."""
        expires_at = time.time() + max(0, expires_in - skew)
        return cls(
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at,
            refresh_token=refresh_token,
        )

    def is_expired(self, skew: int = 30) -> bool:
        """Check if token has expired."""

        return self.expires_at is not None and (time.time() + skew) >= self.expires_at


class OAuth2RefreshingAuth(AuthStrategy):
    """
    OAuth2 auth with access+refresh token cycling.

    - `fetch_token`: Callable returning a fresh OAuth2Token
    - `refresh_token`: Optional callable returning a fresh OAuth2Token given a refresh token. 
       Only one thread performs refresh.
    """

    def __init__(
        self,
        fetch_token: Callable[[], OAuth2Token],
        refresh_token: Callable[[str], OAuth2Token] | None = None,
        expiry_skew_seconds: int = 30,
    ) -> None:
        self._fetch_token_fn = fetch_token
        self._refresh_token_fn = refresh_token
        self._expiry_skew = expiry_skew_seconds
        self._token: OAuth2Token | None = None
        self._lock = RLock()

    def _ensure_token(self) -> None:
        """Ensure that the token has not expired and refresh if needed."""

        with self._lock:
            if self._token is None:
                self._token = self._fetch_token_fn()
                return
            if self._token.is_expired(self._expiry_skew):
                # Prepare refresh_token flow if available; otherwise fetch a new token
                if self._refresh_token_fn and self._token.refresh_token:
                    self._token = self._refresh_token_fn(self._token.refresh_token)
                else:
                    self._token = self._fetch_token_fn()

    def headers(self) -> Mapping[str, str]:
        """Get auth headers."""
        self._ensure_token()
        if self._token is None:
            raise UnauthorizedError("Auth token was not set")
        return {"Authorization": f"{self._token.token_type} {self._token.access_token}"}

    def refresh(self) -> bool:
        """Proactive refresh if token has expired."""

        with self._lock:
            before = self._token.access_token if self._token else None
            self._ensure_token()
            after = self._token.access_token if self._token else None
            return before != after

    def force_refresh(self):
        """Force a refresh (e.g. after a 401).

        Try refresh_token flow first, then fetch a new token. Returns True if token changed.
        """
        with self._lock:
            before = self._token.access_token if self._token else None
            if self._token and self._refresh_token_fn and self._token.refresh_token:
                self._token = self._refresh_token_fn(self._token.refresh_token)
            else:
                self._token = self._fetch_token_fn()
            after = self._token.access_token if self._token else None
            return before != after
