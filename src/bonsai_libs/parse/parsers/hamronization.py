"""Parse the hAMRonization format.

Kleborate implementation: https://kleborate.readthedocs.io/en/stable/kpsc_modules.html#hamronization-report-for-kleborate
"""

import logging
from itertools import chain
from typing import Any, Literal, TypeAlias

from bonsai_libs.parse.io.delimited import DelimiterRow, is_nullish, normalize_row, read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.base import SoupVersion
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType, SoupType
from bonsai_libs.parse.models.hamronization import (
    BaseSequenceRecord,
    HamronizationEntry,
    InputSequence,
    ReferenceSequence,
)

from .utils import safe_float, safe_int, safe_percent, safe_strand

LOG = logging.getLogger(__name__)

HamronizationEntries: TypeAlias = list[HamronizationEntry]
PercentMode: TypeAlias = Literal["fraction", "percent"]

HAMRONIZATION = AnalysisSoftware.HAMRONIZATION

# Implementation of the specification
# ref: https://github.com/pha4ge/hAMRonization/blob/master/docs/hAMRonization_specification_details.csv
REQUIRED_COLUMNS = {
    "Input_file_name",
    "Gene_symbol",
    "Reference_database_name",
    "Reference_database_version",
    "Software_name",
    "Software_version",
    "Genetic_variation_type",
    "Reference_accession",
}
OPTIONAL_COLUMNS = {
    "Antimicrobial_agent",
    "Coverage",
    "Coverage_depth",
    "Coverage_ratio",
    "Drug_class",
    "Input_gene_length",
    "Input_gene_start",
    "Input_gene_stop",
    "Input_protein_length",
    "Input_protein_start",
    "Input_protein_stop",
    "Input_sequence_ID",
    "Mutation",
    "Predicted_phenotype",
    "Reference_gene_length",
    "Reference_gene_start",
    "Reference_gene_stop",
    "Reference_protein_length",
    "Reference_protein_start",
    "Reference_protein_stop",
    "Resistance_mechanism",
    "Sequence_identity",
    "Strand_orientation",
    "predicted_phenotype_confidence_level",
}


def _get_gene_pos(d: dict[str, Any], prefix: Literal["input", "reference"]) -> BaseSequenceRecord:
    """Get base sequence record info."""
    return BaseSequenceRecord(
        gene_start=safe_int(d.get(f"{prefix}_gene_start")),
        gene_stop=safe_int(d.get(f"{prefix}_gene_stop")),
        gene_length=safe_int(d.get(f"{prefix}_gene_length")),
    )


def _to_qc_row(row: dict[str, Any]) -> HamronizationEntry:
    """Take a row and convert it to a hAMRonization entry."""
    input_seq = InputSequence(
        file_name=row.get("input_file_name"),
        sequence_id=row.get("input_sequence_id"),
        **_get_gene_pos(row, "input").model_dump(mode="json"),
    )
    accnr = row.get("reference_accession") if row.get("reference_accession") else "unknown"
    ref_seq = ReferenceSequence(
        accession=accnr,
        reference_db_id=row.get("reference_database_name"),
        reference_db_version=row.get("reference_database_name"),
        **_get_gene_pos(row, "reference").model_dump(mode="json"),
    )
    # convert strand
    strand_orientation = safe_strand(row.get("strand_orientation"))

    # convert mutation entry. This is specifically for the Kleborate implementation of the specification
    variant_info: dict[str, Any] = {}
    nucleotide_mutations = ("c", "g", "n")
    if (mutation := row.get("mutation")) is not None:
        if isinstance(mutation, str) and mutation.startswith("p."):
            variant_info["protein_mutation"] = mutation
        elif isinstance(mutation, str) and mutation[0] in nucleotide_mutations:
            variant_info["nucleotide_mutation"] = mutation

    gene_symbol = row.get("gene_symbol")

    return HamronizationEntry(
        analysis_software_name=row.get("software_name"),
        analysis_software_version=row.get("software_version"),
        input=input_seq,
        reference=ref_seq,
        gene_name=row.get("gene_name") or gene_symbol,
        gene_symbol=gene_symbol,
        strand_orientation=strand_orientation,
        coverage_percentage=safe_percent(row.get("coverage")),
        coverage_depth=safe_int(row.get("coverage_depth")),
        coverage_ratio=safe_float(row.get("coverage_ratio")),
        sequence_identity=safe_float(row.get("sequence_identity")),
        drug_class=row.get("drug_class"),
        genetic_variation_type=row.get("genetic_variation_type"),
        **variant_info,
    )


def _normalize_row(row: DelimiterRow) -> DelimiterRow:
    """Normalize qc row. Wraps normalize_row"""

    return normalize_row(
        row,
        key_fn=lambda r: r.lower().strip().replace(" ", "_"),
        val_fn=lambda v: None if is_nullish(v) else v,
    )


@register_parser(HAMRONIZATION)
class HAmrOnizationParser(SingleAnalysisParser):
    """hAMRonization parser."""

    software = HAMRONIZATION
    parser_name = "HAmrOnizationParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.AMR
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        strict: bool = True,
        **kwargs: Any,
    ) -> HamronizationEntries | None:
        """Parser implementation."""

        row_iter = read_delimited(source)

        try:
            first_row = next(row_iter)
        except StopIteration:
            self.log_info(f"{self.software} input is empty")
            return None

        self.validate_columns(
            row=first_row,
            required=REQUIRED_COLUMNS,
            optional=OPTIONAL_COLUMNS,
            strict=strict,
        )

        entries: HamronizationEntries = []
        for raw_row in chain([first_row], row_iter):
            row = _normalize_row(raw_row)

            try:
                entries.append(_to_qc_row(row))
            except Exception as e:
                if strict:
                    raise
                self.log_warning(f"Skipping invalid row: {e}")

        return entries

    def get_version(self, source: StreamOrPath) -> SoupVersion | None:
        """Get version of Mykrobe from result."""
        rows_iter = read_delimited(source)
        try:
            first = next(rows_iter)
        except StopIteration:
            self.log_info("Mykrobe input is empty")
            return None

        row = _normalize_row(first)
        entry = _to_qc_row(row)
        return SoupVersion(
            name=entry.analysis_software_name,
            version=entry.analysis_software_version,
            type=SoupType.SW,
        )
