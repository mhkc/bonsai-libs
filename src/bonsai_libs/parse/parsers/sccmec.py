"""Parse sccmec results."""

import logging

from bonsai_libs.parse.io.delimited import DelimiterRow, normalize_nulls, read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.typing import TypingResultSccmec

from .utils import safe_float

LOG = logging.getLogger(__name__)

SCCMEC_TYPER = AnalysisSoftware.SCCMECTYPER
REQUIRED_COLUMNS = {
    "sample",
    "type",
    "subtype",
    "mecA",
    "targets",
    "regions",
    "coverage",
    "hits",
}
OPTIONAL_COLUMNS = {
    "target_schema",
    "target_schema_version",
    "region_schema",
    "region_schema_version",
    "camlhmp_version",
    "params",
    "target_comment",
    "region_comment",
    "comment",
}


def _expand_list(field: str | None) -> list[str]:
    """Expand commad delimited list into a python list."""
    if field is None:
        return []
    return [t.strip() for t in field.split(",")]


def _parse_sccmec_results(row: DelimiterRow) -> TypingResultSccmec:
    """Parase SCCMEC results."""
    targets: list[str] = _expand_list(row["targets"])
    regions: list[str] = _expand_list(row["regions"])
    coverage = [safe_float(c) for c in _expand_list(row["coverage"])]
    hits: list[str] = _expand_list(row["hits"])

    out = TypingResultSccmec(
        type=row["type"],
        subtype=row["subtype"],
        mecA=row["mecA"],
        targets=targets,
        regions=regions,
        target_schema=row.get("target_schema"),
        target_schema_version=row.get("target_schema_version"),
        region_schema=row.get("region_schema"),
        region_schema_version=row.get("region_schema_version"),
        camlhmp_version=row.get("camlhmp_version"),
        coverage=coverage,
        hits=hits,
        target_comment=row.get("target_comment"),
        region_comment=row.get("region_comment"),
        comment=row.get("comment"),
    )
    return out


@register_parser(SCCMEC_TYPER)
class SccMecParser(SingleAnalysisParser):
    """Parse SCC Mec results."""

    software = SCCMEC_TYPER
    parser_name = "SccMecTyper"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.SCCMEC}

    def _parse_one(
        self, source: StreamOrPath, strict_columns: bool = True, **_
    ) -> TypingResultSccmec | dict:
        """Implementation on how to parse a single result."""

        reader = read_delimited(source, delimiter="\t")

        try:
            first_row = next(reader)
        except StopIteration:
            self.log_info(f"{self.software} input is empty")

        first_row = normalize_nulls(first_row)
        self.validate_columns(
            first_row,
            required=REQUIRED_COLUMNS,
            optional=OPTIONAL_COLUMNS,
            strict=strict_columns,
        )

        rows = [first_row] + [normalize_nulls(r) for r in reader]
        results = [_parse_sccmec_results(row) for row in rows]
        return results if results else {}
