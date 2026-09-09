"""Parse AMRfinder plus result."""

import itertools
import logging
import re
from typing import Any, TypeAlias

from bonsai_libs.parse.io.delimited import normalize_nulls, read_delimited
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import run_as_envelope
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.base import ElementTypeResult, PhenotypeInfo
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    AnnotationType,
    ElementType,
)
from bonsai_libs.parse.models.phenotype import (
    AmrFinderGene,
    AmrFinderResistanceGene,
    AmrFinderVariant,
    AmrFinderVirulenceGene,
)

from .utils import classify_variant_type, safe_float, safe_int, safe_strand

LOG = logging.getLogger(__name__)

AmrFinderGeneT: TypeAlias = AmrFinderGene | AmrFinderVirulenceGene | AmrFinderVirulenceGene
AmrFinderGenes: TypeAlias = list[AmrFinderGeneT]
AmrFinderVariants: TypeAlias = list[AmrFinderVariant]


AMRFINDER = AnalysisSoftware.AMRFINDER


# Column names as they appear in AMRFinder v4+ output.
V4_COLUMN_MAP: dict[str, str] = {
    "Contig id": "contig_id",
    "Element symbol": "gene_symbol",
    "Element name": "sequence_name",
    "Type": "element_type",
    "Subtype": "element_subtype",
    "Target length": "target_length",
    "Reference sequence length": "ref_seq_len",
    "% Coverage of reference": "ref_seq_cov",
    "% Identity to reference": "ref_seq_identity",
    "Alignment length": "align_len",
    "Closest reference accession": "close_seq_accn",
    "Closest reference name": "close_seq_name",
    # fields used downstream but not renamed:
    "Start": "Start",
    "Stop": "Stop",
    "Strand": "Strand",
    "Method": "Method",
    "Class": "Class",
    "Subclass": "Subclass",
}
V4_DROP_COLUMNS: frozenset[str] = frozenset({"Protein id", "HMM accession", "HMM description"})

# Column names as they appear in AMRFinder v3 output.
V3_COLUMN_MAP: dict[str, str] = {
    "Contig id": "contig_id",
    "Gene symbol": "gene_symbol",
    "Sequence name": "sequence_name",
    "Element type": "element_type",
    "Element subtype": "element_subtype",
    "Target length": "target_length",
    "Reference sequence length": "ref_seq_len",
    "% Coverage of reference sequence": "ref_seq_cov",
    "% Identity to reference sequence": "ref_seq_identity",
    "Alignment length": "align_len",
    "Accession of closest sequence": "close_seq_accn",
    "Name of closest sequence": "close_seq_name",
    # fields used downstream but not renamed:
    "Start": "Start",
    "Stop": "Stop",
    "Strand": "Strand",
    "Method": "Method",
    "Class": "Class",
    "Subclass": "Subclass",
}
V3_DROP_COLUMNS: frozenset[str] = frozenset({"Protein identifier", "HMM id"})

# Case insensitive pattern for variants like "A123T"
VARIANT_PATTERN = re.compile(r"([A-Za-z]+)(\d+)([A-Za-z]+)$")


def _normalize_row(
    raw: dict[str, Any],
    column_map: dict[str, str],
    drop_columns: frozenset[str],
) -> dict[str, Any]:
    """Normalize an AMRFinder row by
    - drop unused columns
    - rename columns to internal names
    - convert empty strings to null values
    """
    raw = {col_name: val for col_name, val in raw.items() if col_name not in drop_columns}
    raw = normalize_nulls(raw)

    normalized: dict[str, Any] = {}
    for src, dest in column_map.items():
        if src in raw:
            normalized[dest] = raw[src]
        else:
            # Keep missing keys as None and handle errors downstream
            normalized[dest] = None
    return normalized


def _phenotypes_from_hit(hit: dict[str, Any], *, element_type: ElementType) -> list[PhenotypeInfo]:
    """
    Extract phenotype annotations from 'Class' and 'Subclass'.
    Returns an empty list if information is missing.
    """
    if element_type != ElementType.AMR:
        return []

    group = (hit.get("Class") or "").lower()
    subclass = hit.get("Subclass") or ""
    if not subclass:
        return []

    return [
        PhenotypeInfo(
            type=element_type,
            group=group,
            name=annot.lower(),
            annotation_type=AnnotationType.TOOL,
        )
        for annot in subclass.split("/")
        if annot
    ]


def _gene_model_for_element_type(element_type: ElementType):
    """Pick the correct gene model class based on element_type."""
    match element_type:
        case ElementType.VIR:
            return AmrFinderVirulenceGene
        case ElementType.AMR:
            return AmrFinderResistanceGene
        case _:
            return AmrFinderGene


def _parse_gene(hit: dict[str, Any]) -> AmrFinderGeneT:
    """Build a gene model from a normalized hit dict."""
    element_type = ElementType(hit["element_type"]) if hit.get("element_type") else ElementType.AMR
    gene_cls = _gene_model_for_element_type(element_type)

    gene = gene_cls(
        gene_symbol=hit["gene_symbol"],
        accession=hit["close_seq_accn"],
        sequence_name=hit["sequence_name"],
        element_type=element_type,
        element_subtype=hit["element_subtype"],
        contig_id=hit["contig_id"],
        query_start_pos=safe_int(hit["Start"]),
        query_end_pos=safe_int(hit["Stop"]),
        strand=safe_strand(hit["Strand"]),
        ref_gene_length=safe_int(hit["ref_seq_len"]),
        alignment_length=safe_int(hit["align_len"]),
        method=hit["Method"],
        identity=safe_float(hit["ref_seq_identity"]),
        coverage=safe_float(hit["ref_seq_cov"]),
    )

    phenotypes = _phenotypes_from_hit(hit, element_type=element_type)
    if phenotypes:
        gene = gene.model_copy(update={"phenotypes": phenotypes})
    return gene


def _parse_variant(hit: dict[str, Any], variant_no: int) -> AmrFinderVariant:
    """Build a variant model from a normalized hit dict."""
    gene_symbol = hit.get("gene_symbol") or ""
    try:
        gene_name, variant = gene_symbol.split("_", 1)
    except ValueError as exc:
        raise ValueError(f"Unrecognized gene_symbol format for variant: {gene_symbol}") from exc

    match = VARIANT_PATTERN.match(variant)
    if not match:
        raise ValueError(f"Unrecognized variant format: {variant}")

    ref_aa, pos, alt_aa = match.groups()
    var_type, var_subtype = classify_variant_type(ref_aa, alt_aa, nucleotide=False)

    phenotypes = _phenotypes_from_hit(hit, element_type=ElementType.AMR)
    pos_i = int(pos)

    return AmrFinderVariant(
        id=variant_no,
        variant_type=var_type,
        variant_subtype=var_subtype,
        reference_sequence=gene_name,
        accession=hit["close_seq_accn"],
        ref_aa=ref_aa,
        alt_aa=alt_aa,
        start=pos_i,
        end=pos_i + (len(alt_aa) - 1),
        contig_id=hit["contig_id"],
        query_start_pos=safe_int(hit["Start"]),
        query_end_pos=safe_int(hit["Stop"]),
        strand=safe_strand(hit["Strand"]),
        ref_gene_length=safe_int(hit["ref_seq_len"]),
        alignment_length=hit["align_len"],
        method=hit["Method"],
        identity=safe_float(hit["ref_seq_identity"]),
        coverage=safe_float(hit["ref_seq_cov"]),
        passed_qc=True,
        phenotypes=phenotypes,
    )


def read_amrfinder_results(
    source: StreamOrPath,
    column_map: dict[str, str],
    drop_columns: frozenset[str],
) -> tuple[AmrFinderGenes, AmrFinderVariants]:
    """Read AMRFinder TSV and return parsed gene hits and point variants.

    source can be a path or a binary stream.
    column_map and drop_columns select the v3 or v4 header mapping."""
    genes: AmrFinderGenes = []
    variants: AmrFinderVariants = []
    var_no = 1

    for raw_row in read_delimited(source, delimiter="\t"):
        hit = _normalize_row(raw_row, column_map, drop_columns)

        if hit.get("element_subtype") == "POINT":
            variants.append(_parse_variant(hit, variant_no=var_no))
            var_no += 1
        else:
            genes.append(_parse_gene(hit))
    return genes, variants


def _analysis_to_element_type(analysis_type: AnalysisType) -> ElementType:
    """
    Map analysis types to ElementType categories for filtering genes.
    AMR and STRESS are treated as AMR element type in the underlying AMRFinder output.
    """
    return (
        ElementType.AMR
        if analysis_type in (AnalysisType.AMR, AnalysisType.STRESS)
        else ElementType.VIR
    )


def _to_resistance_results(
    genes: AmrFinderGenes, variants: AmrFinderVariants, *, analysis_type: AnalysisType
) -> ElementTypeResult:
    """Build AMR/STRES resistance blocks."""

    # filter genes on variants on AMR
    element_type = _analysis_to_element_type(analysis_type)

    filtered_genes = (gene for gene in genes if gene.element_type == element_type)
    filtered_genes = sorted(
        filtered_genes,
        key=lambda gene: (gene.gene_symbol, gene.coverage),
    )

    # Only compute phenotype profile for AMR
    phenotypes = {}
    if analysis_type == AnalysisType.AMR:
        resistant = {
            pheno.name
            for elem in itertools.chain(filtered_genes, variants)
            for pheno in elem.phenotypes
        }
        phenotypes = {"susceptible": [], "resistant": sorted(resistant)}

    return ElementTypeResult(
        phenotypes=phenotypes,
        genes=filtered_genes,
        variants=variants,
    )


def _to_virulence_results(genes) -> ElementTypeResult:
    """Build virulence result block."""

    filtered_genes = [gene for gene in genes if gene.element_type == ElementType.VIR]
    filtered_genes.sort(key=lambda gene: (gene.gene_symbol, gene.coverage))
    return ElementTypeResult(phenotypes={}, genes=filtered_genes, variants=[])


class _AmrFinderParserBase(BaseParser):
    """Shared parse logic for all AMRFinder versions.

    Subclasses select the correct column map for their version range via the
    class attributes ``_column_map`` and ``_drop_columns``; the registry then
    dispatches to the right subclass based on ``software_version`` in the
    sample manifest.
    """

    software = AMRFINDER
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.AMR, AnalysisType.VIRULENCE, AnalysisType.STRESS}

    _column_map: dict[str, str]
    _drop_columns: frozenset[str]

    def _parse_impl(self, source: StreamOrPath, *, want: set[AnalysisType], **_) -> ParseImplOut:
        genes, variants = read_amrfinder_results(source, self._column_map, self._drop_columns)

        base_meta = {"parser": self.parser_name, "software": self.software}

        results: dict[AnalysisType, Any] = {}
        for analysis_type in [AnalysisType.AMR, AnalysisType.STRESS]:
            if analysis_type in want:
                results[analysis_type] = run_as_envelope(
                    analysis_name=analysis_type,
                    fn=lambda at=analysis_type: _to_resistance_results(
                        genes, variants, analysis_type=at
                    ),
                    reason_if_absent=f"{analysis_type} not present",
                    reason_if_empty="No findings",
                    meta=base_meta,
                    logger=self.logger,
                )

        if AnalysisType.VIRULENCE in want:
            results[AnalysisType.VIRULENCE] = run_as_envelope(
                analysis_name=AnalysisType.VIRULENCE,
                fn=lambda: _to_virulence_results(genes),
                reason_if_absent=f"{AnalysisType.VIRULENCE} not present",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )

        return results


@register_parser(AMRFINDER, max_version="3.99.99")
class AmrFinderV3Parser(_AmrFinderParserBase):
    """Parse AMRFinder v3 output (pre-v4 column headers)."""

    parser_name = "AmrFinderV3Parser"
    _column_map = V3_COLUMN_MAP
    _drop_columns = V3_DROP_COLUMNS


@register_parser(AMRFINDER, min_version="4.0.0")
class AmrFinderParser(_AmrFinderParserBase):
    """Parse AMRFinder v4+ output."""

    parser_name = "AmrFinderParser"
    _column_map = V4_COLUMN_MAP
    _drop_columns = V4_DROP_COLUMNS
