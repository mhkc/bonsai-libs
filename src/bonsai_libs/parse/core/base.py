"""Base parser functionality."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from logging import Logger, getLogger
from typing import Any, Mapping, Type, TypeVar

from bonsai_libs.parse.io.delimited import read_delimited, validate_fields
from bonsai_libs.parse.io.types import DelimiterRow, StreamOrPath
from bonsai_libs.parse.core.envelope import (
    default_empty_predicate,
    envelope_absent,
    envelope_skipped,
    run_as_envelope,
)
from bonsai_libs.parse.exceptions import UnsupportedAnalysisTypeError
from bonsai_libs.parse.models.enums import AnalysisType, ResultStatus

T = TypeVar("T")


class BaseParser(ABC):
    """Parser class structure."""

    software: str
    parser_name: str
    parser_version: int
    schema_version: int
    produces: set[AnalysisType]

    def __init__(self, *, logger: Logger | None = None):
        self.logger = logger or getLogger(f"bonsai_libs.parse.{self.parser_name}")

    def log_info(self, msg: str, **ctx):
        """Log info message with context."""

        self.logger.info(msg, extra={"context": ctx})

    def log_warning(self, msg: str, **ctx):
        """Log warning message with context."""
        self.logger.warning(msg, extra={"context": ctx})

    def log_error(self, msg: str, **ctx):
        """Log error message with context."""
        self.logger.error(msg, extra={"context": ctx})

    def parse(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType] | AnalysisType | None = None,
        software_version: str | None = None,
        **kwargs: Any,
    ) -> "ParserOutput":
        """Parse a source into structured results."""
        want: set[AnalysisType] = self._normalize_want(want)

        out = self._new_output(software_version)

        # prepopulate with result envelopes for what this parser can produce
        for atype in self.produces:
            if want is not None and atype not in want:
                out.results[atype] = envelope_skipped()
            else:
                # The specific parser implementation will have to clarify
                # why a analysis was absent
                out.results[atype] = envelope_absent(reason="Prepopulated")

        # exit if the parser cant produce what is requested
        requested = want & self.produces
        if not requested:
            self.log_info(
                "Skipping parse; parser cant produce requested output",
                requested=[w.value for w in want],
                produces=[p.value for p in self.produces],
            )
            raise UnsupportedAnalysisTypeError(
                "Skipping parse; parser cant produce requested output",
                context={
                    "requested": [w.value for w in want],
                    "produces": [p.value for p in self.produces],
                },
            )

        self.log_info("Parsing", software=self.software, parser=self.parser_name)

        # Let the subclasses implement the core logic
        results = self._parse_impl(source, want=requested, **kwargs)

        # Merge results in a predictable structure
        out.results.update(results)
        return out

    def _normalize_want(self, want: set[AnalysisType] | AnalysisType | None) -> set[AnalysisType]:
        """Normalize the want parameter to a set of AnalysisType."""

        want = want or set(self.produces)
        return {want} if isinstance(want, AnalysisType) else want

    def _new_output(self, software_version: str | None) -> "ParserOutput":
        """Create a new output model."""
        # lazy load to avoid circular imports
        from bonsai_libs.parse.models.base import ParserOutput

        return ParserOutput(
            software=self.software,
            software_version=software_version,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            schema_version=getattr(self, "schema_version", 1),
            results={},
        )

    def validate_columns(
        self,
        row: Mapping[str, object],
        *,
        required: set[str],
        optional: set[str] | None = None,
        strict: bool = False,
        tool: str | None = None,
    ) -> None:
        """Thin wrapper of the validate_fields to setup logging."""
        try:
            validate_fields(row, required=required, optional=optional, strict=strict)
        except ValueError as exc:
            self.log_error(
                "Schema validation failed",
                software=self.software,
                tool=tool or self.software,
                required=sorted(required),
                got=sorted(row.keys()),
                strict=strict,
                error=str(exc),
            )
            raise

    # generic helpers ---------------------------------------------------------

    def _read_rows(
        self,
        source: StreamOrPath,
        *,
        required: set[str] | None = None,
        strict_columns: bool = False,
    ) -> tuple[Mapping[str, Any] | None, Iterator[DelimiterRow] | None]:
        """Read a delimited source, validate header and return iterator.

        Returns a ``(first_row, rows_iterator)`` pair.  ``first_row`` will be
        ``None`` if the source is empty; in that case both elements of the tuple
        are ``None`` and the caller should bail out.  ``required`` is an
        optional set of column names to validate against the first row.  The
        columns are validated via :meth:`validate_columns`, so any resulting
        exception is propagated.
        """
        rows = read_delimited(source)
        try:
            first = next(rows)
        except StopIteration:
            self.log_info(f"{self.software} input empty")
            return None, None
        if required:
            self.validate_columns(first, required=required, strict=strict_columns)
        return first, rows

    def _get_first_normalized_row(
        self,
        source: StreamOrPath,
        column_map: dict[str, str],
        *,
        required: set[str] | None = None,
        strict_columns: bool = False,
        max_consume: int = 10,
    ) -> Mapping[str, Any] | None:
        """Convenience: read, validate and normalize a single delimited row.

        ``column_map`` is passed through to :func:`bonsai_libs.parse.io.delimited.normalize_row`.
        If the source is empty this returns ``None``.  Extra rows are consumed up
        to ``max_consume`` and a warning emitted via :meth:`log_warning`.
        """
        first, rows = self._read_rows(source, required=required, strict_columns=strict_columns)
        if first is None:
            return None
        # normalization is a very common pattern; import lazily to avoid a
        # circular dependency during package import.
        from bonsai_libs.parse.io.delimited import is_nullish, normalize_row

        normalized = normalize_row(
            first,
            key_fn=lambda r: r.strip(),
            val_fn=lambda v: None if is_nullish(v) else v,
            column_map=column_map,
        )
        warn_if_extra_rows(
            rows,
            self.log_warning,
            context=f"{self.software} file",
            max_consume=max_consume,
        )
        return normalized

    @abstractmethod
    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        **kwargs: Any,
    ) -> "ParseImplOut":
        """Return results keyed by analysis_type."""


class SingleAnalysisParser(BaseParser):
    """Abtracted parser class for softwares that produces exactly one AnalysisType"""

    subcommand: str | None = None
    """Optional subcommand identifier used when one software binary produces
    multiple distinct output formats (e.g. 'coverage' and 'stats' for samtools).
    The registry uses (software, subcommand) as a composite key so each output
    type can have its own parser class."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "produces") or len(cls.produces) != 1:
            raise TypeError(f"{cls.__name__}.produces must contain exactly one AnalysisType")

    @property
    def analysis_type(self) -> AnalysisType:
        """Get analysis type from what the parser produce."""
        return next(iter(self.produces))

    def empty_predicate(self) -> Callable[[Any], bool]:
        """Allow subclasses to override how "empty" is determined."""
        return default_empty_predicate

    def absent_predicate(self) -> Callable[[Any], bool] | None:
        """Optional hook if a subclass prefers a value-based absent detection.

        This instead of raising AbsentResultError."""
        return None

    def _parse_impl(
        self, source: StreamOrPath, *, want: set[AnalysisType], **kwargs: Any
    ) -> Mapping[str, Any]:
        env = run_as_envelope(
            analysis_name=self.analysis_type,
            fn=lambda: self._parse_one(source, **kwargs),
            empty_predicate=self.empty_predicate(),
            absent_predicate=self.absent_predicate(),
            reason_if_absent=f"{self.analysis_type} not present",
            reason_if_empty="No findings",
            meta={"parser": self.parser_name, "software": self.software},
            logger=self.logger,
        )
        return {self.analysis_type: env}

    @abstractmethod
    def _parse_one(self, source: StreamOrPath, **kwargs: Any) -> Any: ...


def warn_if_extra_rows(
    rows: Iterator[T],
    warn: Callable[[str], None],
    *,
    context: str = "input",
    max_consume: int = 10,
    warn_at: int = 1,
) -> int:
    """
    Consume up to `max_consume` additional rows from an iterator and warn once
    if there is more than one row.

    Returns number of extra rows consumed (0 if none).

    - `warn_at`: warn when extra_rows reaches this number (default 1)
    - `max_consume`: hard cap to avoid exhausting huge streams
    """
    extra = 0
    for _ in rows:
        extra += 1
        if extra == warn_at:
            warn(f"{context} has multiple rows; using first row only")
        if extra >= max_consume:
            break
    return extra


ParserClass = Type[BaseParser]


def parse_child(
    parser: BaseParser, source: StreamOrPath, atype: AnalysisType, *, strict: bool
) -> Any:
    """Utility to call another parser inside a parser."""

    # lazy load deps to avoid circular imports
    from bonsai_libs.parse.models.base import ResultEnvelope

    child = parser.parse(source, want={atype}, strict=strict)
    env = child.results.get(atype)
    if env and isinstance(env, ResultEnvelope) and env.status == ResultStatus.PARSED:
        return env.value
    return None
