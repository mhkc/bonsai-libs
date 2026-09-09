"""Common errors"""

from typing import Any


class ParserError(Exception):
    """Base exception for parsers of analysis results."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.context = context or {}


class DataFormatError(ParserError):
    """Generic data/serialization errors (IO-level)."""


class InvalidDataFormat(ParserError):
    """Fatal: content present but corrupted/ill-formed -> ERROR."""


class UnsupportedAnalysisTypeError(ParserError):
    """Usually not thrown if 'produces' is configured; if thrown, treat as ERROR or SKIPPED policy-wise."""


class SchemaMismatchError(ParserError):
    """Fatal: required schema/columns do not match -> ERROR."""


class UnsupportedSoftwareError(ParserError):
    """Fatal (or map to SKIPPED at a higher level if you prefer) -> ERROR by default."""


class UnsupportedVersionError(ParserError):
    """Fatal (or map to SKIPPED at a higher level if you prefer) -> ERROR by default."""


class AbsentResultError(ParserError):
    """Non-fatal: the assay/section is not present in the input."""
