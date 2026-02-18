"""The base API client that can be extended to use for different services."""

import logging
import random
import time
from abc import ABC
from collections.abc import Iterable
from http import HTTPStatus
from typing import Any, Literal

import requests

from .exceptions import ApiRequestFailed, UnauthorizedError, raise_for_status
from .auth import AuthStrategy

LOG = logging.getLogger(__name__)


RequestMethods = Literal["GET", "POST", "PUT", "DELETE"]

JSONData = dict[str, Any]


class BaseClient(ABC):
    """Base API client."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 5.0,
        retries: int = 2,
        backoff: float = 0.2,
        max_backoff: float = 0.5,
        default_headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
        auth: AuthStrategy | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.max_backoff = max_backoff
        self.session = session or requests.Session()
        self.default_headers = dict(default_headers or {})
        self.auth = auth

    def _request(
        self,
        method: RequestMethods,
        path: str,
        *,
        expected_status: Iterable[int] = (200,),
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> JSONData | str | None:
        """Base request class"""
        api_url = f"{self.base_url}/{path}"
        attempts = self.retries + 1

        # merge headers
        combined_headers: dict[str, str] = {}
        combined_headers.update(self.default_headers)
        if headers:
            combined_headers.update(headers)

        # Add auth headers
        if self.auth is not None:
            try:
                combined_headers.update(self.auth.headers())
            except Exception as exc:
                LOG.exception("Auth header generation failed: %s", exc)

        did_force_refresh = False  # ensure only one force refresh per request

        for attempt in range(1, attempts + 1):
            LOG.info("Request: %s %s - attempt %d", method, api_url, attempt)
            try:
                resp = self.session.request(
                    method,
                    api_url,
                    headers=combined_headers,
                    timeout=timeout or self.timeout,
                    **kwargs,
                )

                # Handle 401 error; attempt one forced refresh if implemented and then retry
                if all(
                    [
                        resp.status_code == HTTPStatus.UNAUTHORIZED,
                        self.auth is not None,
                        not did_force_refresh,
                    ]
                ):
                    LOG.warning("401 recieved, appempting token refresh and retry")
                    try:
                        if self.auth.did_force_refresh():
                            # update combined headers with new auth token
                            combined_headers.update(self.auth.headers())
                        did_force_refresh = True
                        # retry call
                        continue
                    except Exception as exc:
                        LOG.exception("Token refresh failed, %s", exc)
                        raise UnauthorizedError("Authentication failed") from exc

                if resp.status_code not in expected_status:
                    raise_for_status(resp.status_code, resp.text)

                # parse response
                if resp.status_code == HTTPStatus.NO_CONTENT or resp.content is None:
                    return None
                content_type = resp.headers.get("Content-Type", "").lower()
                if "application/json" in content_type:
                    return resp.json()
                return resp.text  # resturn as string
            except (requests.ConnectionError, requests.Timeout):
                LOG.debug(
                    "Request attempt %d failed retrying %d times",
                    attempt,
                    attempts,
                    extra={"url": api_url},
                )
                self._sleep_with_jitter(attempt)
        raise ApiRequestFailed(f"Request {method} {api_url} failed")

    def _sleep_with_jitter(self, attempt: int) -> None:
        """Sleep time with a small jitter.

        Spaces out multiple request."""
        base = self.backoff * (2 ** (attempt - 1))
        sleep = random.uniform(0, min(self.max_backoff, base))
        time.sleep(sleep)

    # helper methods
    def get(self, path: str, **kwargs: Any):
        """Get request to entrypoint."""
        LOG.debug("Request: GET %s; params: %s", path, kwargs)
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any):
        """POST request to entrypoint."""
        LOG.debug("Request: POST %s; params: %s", path, kwargs)
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any):
        """PUT request to entrypoint."""
        LOG.debug("Request: PUT %s; params: %s", path, kwargs)
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any):
        """DELETE request to entrypoint."""
        LOG.debug("Request: DELETE %s; params: %s", path, kwargs)
        return self._request("DELETE", path, **kwargs)
