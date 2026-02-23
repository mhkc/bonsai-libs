"""Shared response handling for API clients."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiResponse:
    """Structured API response."""

    status: int
    data: Any
    raw: Any
    headers: dict[str, str]

    @property
    def ok(self) -> bool:
        """Indicates if the response status code is in the 2xx range."""

        return 200 <= self.status < 300

    @property
    def json(self):
        """Return the response data as JSON if possible."""
        return self.data if isinstance(self.data, dict) else None

    def get(self, key: str, default=None):
        """Convenience method to get a value from the JSON data."""

        if isinstance(self.data, dict):
            return self.data.get(key, default)
        return default