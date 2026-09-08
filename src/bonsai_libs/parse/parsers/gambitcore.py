"""Parse gambitcore results."""

import re
from typing import Any

from bonsai_libs.parse.io.delimited import DelimiterRow, is_nullish, normalize_row, read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath, warn_if_extra_rows
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType, GambitcoreQcFlag
from bonsai_libs.parse.models.qc import GambitcoreQcResult

from .utils import safe_int, safe_percent

GAMBITCORE = AnalysisSoftware.GAMBITCORE

COLUMN_MAP = {
    "Species": "scientific_name",
    "Completeness (%)": "completeness",
    "Assembly Core/species Core": "assembly_core",
    "Closest accession": "closest_accession",
    "Closest distance": "closest_distance",
    "Assembly Kmers": "assembly_kmers",
    "Species Kmers Mean": "species_kmers_mean",
    "Species Kmers Std Dev": "species_kmers_std_dev",
    "Assembly QC": "assembly_qc",
}

# pattern for (int/int)
CORE_PATTERN = re.compile(r"\((?P<assembly>\d+)/(?P<reference>\d+)\)")


def _normalize_gambitcore_row(row: DelimiterRow) -> DelimiterRow:
    """Wrapps normalize row."""

    return normalize_row(
        row,
        key_fn=lambda r: r.strip(),
        val_fn=lambda v: None if is_nullish(v) else v,
        column_map=COLUMN_MAP,
    )


def _to_qc_result(row: dict[str, Any]) -> GambitcoreQcResult:
    """Convert and validate row into Spatyper result object."""
    qc_flag = GambitcoreQcFlag(row.get("assembly_qc", "red"))

    assembly_core = spp_core = None
    if m := CORE_PATTERN.search(row.get("assembly_core", "") or ""):
        assembly_core = safe_int(m.group("assembly"))
        spp_core = safe_int(m.group("reference"))

    return GambitcoreQcResult(
        scientific_name=row["scientific_name"],
        completeness=safe_percent(row.get("completeness")),
        assembly_core=assembly_core,
        species_core=spp_core,
        closest_accession=row["closest_accession"],
        closest_distance=row["closest_distance"],
        assembly_kmers=row["assembly_kmers"],
        species_kmers_mean=row["species_kmers_mean"],
        species_kmers_std_dev=row["species_kmers_std_dev"],
        assembly_qc=qc_flag,
    )


@register_parser(GAMBITCORE)
class GambitcoreParser(SingleAnalysisParser):
    """Gambitcore parser."""

    software = GAMBITCORE
    parser_name = "GambitcoreParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.QC
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        strict: bool = False,
        **kwargs: Any,
    ) -> GambitcoreQcResult | None:
        """Parse gambitcore csv and return GambitcoreQcResult."""

        rows = read_delimited(source, delimiter="\t")
        try:
            first_raw = next(rows)
        except StopIteration:
            self.log_info(f"{self.software} input empty")
            return None

        required_cols = set(COLUMN_MAP)
        self.validate_columns(first_raw, required=required_cols, strict=strict)
        first = _normalize_gambitcore_row(first_raw)
        warn_if_extra_rows(rows, self.log_warning, context=f"{self.software} file", max_consume=10)

        return _to_qc_result(first)
