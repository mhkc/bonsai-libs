"""Parse spaTyper results."""

from typing import Any

from bonsai_libs.parse.io.delimited import DelimiterRow, is_nullish, read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath, warn_if_extra_rows
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.typing import TypingResultSpatyper

from .utils import normalize_delimited_row

SPATYPER = AnalysisSoftware.SPATYPER

REQUIRED_COLUMNS: set[str] = {"Sequence name", "Repeats", "Type"}
COLUMN_MAP = {
    "Sequence name": "sequence_name",
    "Repeats": "repeats",
    "Type": "type",
}


def _normalize_spatyper_row(row: DelimiterRow) -> DelimiterRow:
    """Wrapper kept for backwards compatibility; delegates to shared helper."""
    from .utils import normalize_delimited_row

    return normalize_delimited_row(row, COLUMN_MAP)


def _to_typing_result(row: dict[str, Any]) -> TypingResultSpatyper:
    """Convert and validate row into Spatyper result object."""
    repeats = row.get("repeats")  # possibly split repeats on '-'
    return TypingResultSpatyper(
        sequence_name=row["sequence_name"],
        repeats=repeats,
        type=row["type"],
    )


@register_parser(SPATYPER)
class SpatyperParser(SingleAnalysisParser):
    """Parser for ShigaType results."""

    software = SPATYPER
    parser_name = "SpatyperParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.SPATYPE
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        strict_columns: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> TypingResultSpatyper | None:
        """Parse SpaTyper output and return a TypingResultSpatyper."""
        first = self._get_first_normalized_row(
            source,
            COLUMN_MAP,
            required=REQUIRED_COLUMNS,
            strict_columns=strict_columns,
        )
        if first is None:
            return None

        # Build typing result
        return _to_typing_result(first)
