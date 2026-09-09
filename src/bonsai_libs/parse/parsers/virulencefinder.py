"""Functions for parsing virulencefinder result."""

import logging
from typing import Any

from bonsai_libs.parse.io.json import read_json, require_mapping
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import run_as_envelope
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import InvalidDataFormat
from bonsai_libs.parse.models.base import ElementTypeResult, GeneWithReference
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    ElementType,
    ElementVirulenceSubtype,
)

LOG = logging.getLogger(__name__)

VIRFINDER = AnalysisSoftware.VIRULENCEFINDER

REQUIRED_FIELDS = {"databases", "seq_regions", "software_executions"}


def parse_vir_gene(
    info: dict[str, Any],
    function: str,
    subtype: ElementVirulenceSubtype = ElementVirulenceSubtype.VIR,
) -> GeneWithReference:
    """Parse virulence gene prediction results."""
    accnr = info.get("ref_acc", None)
    if accnr == "NA":
        accnr = None
    return GeneWithReference(
        # info
        gene_symbol=info["name"],
        accession=accnr,
        sequence_name=function,
        # gene classification
        element_type=ElementType.VIR,
        element_subtype=subtype,
        # position
        ref_start_pos=int(info["ref_start_pos"]),
        ref_end_pos=int(info["ref_end_pos"]),
        ref_gene_length=int(info["ref_seq_length"]),
        alignment_length=int(info["alignment_length"]),
        # prediction
        identity=float(info["identity"]),
        coverage=float(info["coverage"]),
    )


def pick_best_region(regions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the region with highest coverage and identity."""

    if not regions:
        return None
    return max(regions, key=lambda region: (region["coverage"], region["identity"]))


def parse_stx_typing(pred: dict[str, Any]) -> GeneWithReference | None:
    """Parse STX typing from virulencefinder's output."""

    phenotypes = pred.get("phenotypes", {}) or {}
    seq_regions = pred.get("seq_regions", {}) or {}

    stx_keys = [k for k in phenotypes.keys() if str(k).lower().startswith("stx")]
    if not stx_keys:
        return None

    best_gene: GeneWithReference | None = None
    best_score: tuple[float, float] = (0.0, 0.0)

    for stx_key in stx_keys:
        pheno = phenotypes.get(stx_key) or {}
        function = pheno.get("function") or ""
        region_keys = pheno.get("seq_regions") or []
        regions = [seq_regions.get(k) for k in region_keys if seq_regions.get(k)]
        best_region = pick_best_region(regions)
        if not best_region:
            continue

        gene = parse_vir_gene(best_region, function=function)
        score = (float(gene.identity or 0.0), float(gene.coverage or 0.0))
        if score > best_score:
            best_score = score
            best_gene = GeneWithReference(**gene.model_dump())

    return best_gene


def parse_virulence_block(pred: dict[str, Any]) -> ElementTypeResult:
    """Parse virulencefinder virulence prediction results."""

    vir_genes: list[GeneWithReference] = []
    phenotypes = pred.get("phenotypes", {}) or {}
    seq_regions = pred.get("seq_regions", {}) or {}

    for _, pheno in phenotypes.items():
        function = pheno.get("function") or ""
        ref_dbs = pheno.get("ref_database") or []

        # skip stx typing results
        if any("stx" in str(db).lower() for db in ref_dbs):
            continue

        subtype = ElementVirulenceSubtype.VIR
        if any("toxin" in str(db).lower() for db in ref_dbs):
            subtype = ElementVirulenceSubtype.TOXIN

        region_keys = pheno.get("seq_regions") or []
        regions = [seq_regions.get(k) for k in region_keys if seq_regions.get(k)]
        for info in regions:
            vir_genes.append(parse_vir_gene(info, function=function, subtype=subtype))

    # stable sort, handle None safely if coverage can be None
    vir_genes.sort(
        key=lambda g: (
            g.gene_symbol or "",
            g.coverage if g.coverage is not None else -1.0,
        )
    )

    return ElementTypeResult(genes=vir_genes, variants=[], phenotypes={})


@register_parser(VIRFINDER)
class VirulenceFinderParser(BaseParser):
    """VirulenceFinder parser."""

    software = VIRFINDER
    parser_name = "VirulenceFinderParser"
    parser_version = "1"
    schema_version = "1"
    produces = {AnalysisType.VIRULENCE, AnalysisType.STX}

    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        strict: bool = False,
        **kwargs: Any,
    ) -> ParseImplOut:
        """Parse virulence finder resuls."""
        try:
            raw = read_json(source)
            raw = require_mapping(raw, what="<root>")
            for field in REQUIRED_FIELDS:
                require_mapping(raw.get(field), what=field)

        except TypeError as exc:
            self.log_error("Failed to read SerotypeFinder JSON", error=str(exc))
            if strict:
                raise
            return {}
        except InvalidDataFormat as exc:
            self.log_error("Failed to read/validate VirulenceFinder JSON", error=str(exc))
            if strict:
                raise
            return {}

        out: dict[AnalysisType, Any] = {}

        base_meta = {"parser": self.parser_name, "software": self.software}

        if AnalysisType.VIRULENCE in want:
            out[AnalysisType.VIRULENCE] = run_as_envelope(
                analysis_name=AnalysisType.VIRULENCE,
                fn=lambda: parse_virulence_block(raw),
                reason_if_absent="No virulence determinants in file.",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )

        if AnalysisType.STX in want:
            out[AnalysisType.STX] = run_as_envelope(
                analysis_name=AnalysisType.STX,
                fn=lambda: parse_stx_typing(raw),
                reason_if_absent="No STX gene identified.",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )
        return out
