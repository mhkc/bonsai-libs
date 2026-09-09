"""Parse results from Samtools."""

from itertools import chain
from typing import Any

from bonsai_libs.parse.io.delimited import read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.qc import ContigCoverage, SamtoolsCoverageQcResult

from .utils import normalize_delimited_row, safe_float, safe_int

SAMTOOLS = AnalysisSoftware.SAMTOOLS

COLUMN_MAP = {
    "#rname": "contig_name",
    "startpos": "start_pos",
    "endpos": "end_pos",
    "numreads": "n_reads",
    "covbases": "cov_bases",
    "coverage": "coverage",
    "meandepth": "mean_depth",
    "meanbaseq": "mean_base_quality",
    "meanmapq": "mean_map_quality",
}


def _to_contig_result(row: dict[str, Any]) -> ContigCoverage:
    """Covert data to structured model."""
    return ContigCoverage(
        contig_name=row["contig_name"],
        start_pos=safe_int(row["start_pos"]),
        end_pos=safe_int(row["end_pos"]),
        n_reads=safe_int(row["n_reads"]),
        cov_bases=safe_float(row["cov_bases"]),
        coverage=safe_float(row["coverage"]),
        mean_depth=safe_float(row["mean_depth"]),
        mean_base_quality=safe_float(row["mean_base_quality"]),
        mean_map_quality=safe_float(row["mean_map_quality"]),
    )


@register_parser(SAMTOOLS, subcommand="coverage")
class SamtoolsCovParser(SingleAnalysisParser):
    """Parse samtools coverage output into a SamtoolsCoverageQcResult."""

    software = SAMTOOLS
    subcommand = "coverage"
    parser_name = "SamtoolsCovParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.QC
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        strict: bool = True,
        **kwargs: Any,
    ) -> SamtoolsCoverageQcResult | None:
        """Parse samtools coverage tsv and return SamtoolsCoverageQcResult."""

        first = self._get_first_normalized_row(
            source,
            COLUMN_MAP,
            required=set(COLUMN_MAP),
            strict_columns=strict,
        )
        if first is None:
            return None

        contigs: list[ContigCoverage] = []
        # first is already normalized, so iterate remaining rows normally
        rows_iter = read_delimited(source)
        # skip the first row we've already consumed
        next(rows_iter, None)
        for raw_row in chain([first], rows_iter):
            normed = normalize_delimited_row(raw_row, COLUMN_MAP)
            contigs.append(_to_contig_result(normed))
        return SamtoolsCoverageQcResult(contigs=contigs)
