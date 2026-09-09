"""Parse chewbacca cgMLST result."""

from typing import Any, Mapping

from bonsai_libs.parse.io.delimited import (
    DelimiterRow,
    canonical_header,
    is_nullish,
    normalize_row,
    read_delimited,
)
from bonsai_libs.parse.core.base import SingleAnalysisParser, warn_if_extra_rows
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType, ChewbbacaErrors
from bonsai_libs.parse.models.typing import TypingResultCgMlst

from .utils import safe_int

CHEWBBACA = AnalysisSoftware.CHEWBBACA

REQUIRED_FIELDS = {"FILE"}

ALT_ALLELE_CALLS = [
    "ALM",
    "ASM",
    "EXC",
    "INF",
    "LNF",
    "LOTSC ",
    "NIPH",
    "NIPHEM",
    "PAMA",
    "PLNF",
    "PLOT3",
    "PLOT5",
]


def _normalize_row(row: DelimiterRow) -> DelimiterRow:
    """Wrapps normalize row."""
    return normalize_row(
        row,
        key_fn=lambda r: canonical_header(r).lstrip(","),
        val_fn=lambda v: None if is_nullish(v) else v,
    )


def replace_cgmlst_errors(
    allele: str,
    *,
    include_novel_alleles: bool = True,
    correct_alleles: bool = False,
    log_warn: Any | None = None,
) -> int | str | None:
    """Replace errors and novel allele calls with null values."""
    errors = [err.value for err in ChewbbacaErrors]
    # check input
    match allele:
        case str():
            pass
        case int():
            allele = str(allele)
        case bool():
            allele = str(safe_int(allele))
        case _:
            raise ValueError(f"Unknown file type: {allele}")
    if any(
        [
            correct_alleles and allele in errors,
            correct_alleles and allele.startswith("INF") and not include_novel_alleles,
        ]
    ):
        return None

    if include_novel_alleles:
        if allele.startswith("INF"):
            allele = allele.split("-")[1].replace("*", "")
        else:
            allele = allele.replace("*", "")

    # try convert to an int
    try:
        allele = int(allele)
    except ValueError:
        allele = str(allele)
        if allele not in ALT_ALLELE_CALLS and log_warn is not None:
            log_warn(
                f"Possible cgMLST parser error, allele '{allele}' could not be cast as an integer",
            )
    return allele


def _to_typing_result(row: Mapping[str, Any], *, log_warn: Any | None = None) -> TypingResultCgMlst:
    """Cast result to TypingResultCgMlst."""

    # remove file column
    row.pop("FILE")

    errors = [err.value for err in ChewbbacaErrors]

    n_novel = 0
    n_missing = 0
    corrected_alleles: dict[str, Any] = {}
    for name, allele in row.items():
        if allele.startswith("INF") or allele.startswith("*"):
            n_novel += 1
        if allele in errors:
            n_missing += 1
        corrected_alleles[name] = replace_cgmlst_errors(allele, log_warn=log_warn)

    return TypingResultCgMlst(
        n_novel=n_novel,
        n_missing=n_missing,
        alleles=corrected_alleles,
    )


@register_parser(CHEWBBACA)
class ChewbbacaParser(SingleAnalysisParser):
    """Parse MLST.py results."""

    software = CHEWBBACA
    parser_name = "ChewbbacaParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.CGMLST}

    def _parse_one(self, source, *, strict: bool = False, **kwargs):
        """Parser implementation."""

        # read analysis result
        rows = read_delimited(source, delimiter="\t")

        try:
            first_raw = next(rows)
        except StopIteration:
            self.log_info(f"{self.software} input is empty")
            return None

        # verify data
        self.validate_columns(first_raw, required=REQUIRED_FIELDS)

        # Normalize keys
        first = _normalize_row(first_raw)
        warn_if_extra_rows(rows, self.log_warning, context=f"{self.software} file", max_consume=11)

        # to envelope
        return _to_typing_result(first, log_warn=self.log_warning)
