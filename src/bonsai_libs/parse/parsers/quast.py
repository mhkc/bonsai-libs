"""Parse Quast results."""

from typing import Any

from bonsai_libs.parse.io.delimited import DelimiterRow, is_nullish, read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath, warn_if_extra_rows
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.qc import QuastQcResult

from .utils import safe_float, safe_int

QUAST = AnalysisSoftware.QUAST

REQUIRED_COLUMNS = {
    "Total length",
    "Reference length",
    "Largest contig",
    "# contigs",
    "N50",
    "NG50",
    "GC (%)",
    "Reference GC (%)",
    "Duplication ratio",
}
COLUMN_MAP = {
    "Total length": "total_length",
    "Reference length": "reference_length",
    "Largest contig": "largest_contig",
    "# contigs": "n_contigs",
    "N50": "n50",
    "NG50": "ng50",
    "GC (%)": "gc_perc",
    "Reference GC (%)": "reference_gc_perc",
    "Duplication ratio": "duplication_ratio",
}


def _to_qc_result(row: dict[str, Any]) -> QuastQcResult:
    """Cast row as quast result."""
    return QuastQcResult(
        total_length=safe_int(row["total_length"]),
        reference_length=safe_int(row["reference_length"]),
        largest_contig=safe_int(row["largest_contig"]),
        n_contigs=safe_int(row["n_contigs"]),
        n50=safe_int(row["n50"]),
        ng50=safe_int(row["ng50"]),
        assembly_gc=safe_float(row["gc_perc"]),
        reference_gc=safe_float(row["reference_gc_perc"]),
        duplication_ratio=safe_float(row["duplication_ratio"]),
    )


# normalization is generic; use shared helper instead of repeating the pattern


def _normalize_quast_row(
    row: DelimiterRow,
) -> DelimiterRow:  # kept for backwards compatibility
    """Normalize a single Quast row.

    This wrapper exists to preserve the old name; it delegates to the generic
    ``normalize_delimited_row`` defined in :mod:`.utils` so that identical
    implementations aren't copied into every parser.
    """
    from .utils import normalize_delimited_row

    return normalize_delimited_row(row, COLUMN_MAP)


@register_parser(QUAST)
class QuastParser(SingleAnalysisParser):
    """Parse Quast results."""

    software = QUAST
    parser_name = "QuastParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.QC
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        strict_columns: bool = False,
        **kwargs: Any,
    ) -> QuastQcResult | None:
        """Parse Quast output and return a QuastQcResult."""
        # read and normalise a single row; handles empty file and column
        # validation internally
        first = self._get_first_normalized_row(
            source,
            COLUMN_MAP,
            required=REQUIRED_COLUMNS,
            strict_columns=strict_columns,
        )
        if first is None:
            return None

        # build qc result
        return _to_qc_result(first)
