"""Parse Kleborate results.

Documentation: https://kleborate.readthedocs.io/en/latest/index.html
"""

import re
from enum import StrEnum
from itertools import chain
from typing import Any, Callable, Literal, Mapping

from bonsai_libs.parse.io.delimited import DelimiterRow, is_nullish, normalize_row, read_delimited
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import (
    envelope_absent,
    envelope_error,
    envelope_from_value,
    run_as_envelope,
)
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import AbsentResultError, ParserError
from bonsai_libs.parse.models.base import ElementTypeResult, PhenotypeInfo, ResultEnvelope
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    AnnotationType,
    ElementAmrSubtype,
    ElementType,
    ResultStatus,
    VariantSubType,
    VariantType,
)
from bonsai_libs.parse.models.hamronization import HamronizationEntries, HamronizationEntry
from bonsai_libs.parse.models.kleborate import (
    KleborateEtScore,
    KleborateKaptiveLocus,
    KleborateMlstLikeResults,
    KleborateQcResult,
    KleboreateSppResult,
    ParsedVariant,
)
from bonsai_libs.parse.models.phenotype import AmrFinderResistanceGene, AmrFinderVariant
from bonsai_libs.parse.parsers.hamronization import HAmrOnizationParser

from .utils import safe_int, safe_strand

WarnFn = Callable[[str], None]

REQUIRED_COLUMNS = {"strain"}
COLUMN_MAP = {"strain": "sample_id"}

KLEBORATE = AnalysisSoftware.KLEBORATE


_MLST_LIKE_SCHEMAS: dict[str, dict[str, Any]] = {
    "abst": {
        "lineage_key": "Aerobactin",
        "st_key": "AbST",
        "qc_keys": ["spurious_abst_hits"],
    },
    "cbst": {
        "lineage_key": "Colibactin",
        "st_key": "CbST",
        "qc_keys": ["spurious_clb_hits"],
    },
    "rmst": {
        "lineage_key": "RmpADC",
        "st_key": "RmST",
        "qc_keys": ["spurious_rmst_hits"],
    },
    "smst": {
        "lineage_key": "Salmochelin",
        "st_key": "SmST",
        "qc_keys": ["spurious_smst_hits"],
    },
    "ybst": {
        "lineage_key": "Yersiniabactin",
        "st_key": "YbST",
        "qc_keys": ["spurious_ybt_hits"],
    },
}

_MLST_TO_ANALYSISTYPE: dict[str, AnalysisType] = {
    "abst": AnalysisType.ABST,
    "cbst": AnalysisType.CBST,
    "rmst": AnalysisType.RMST,
    "smst": AnalysisType.SMST,
    "ybst": AnalysisType.YBST,
}


def _compile(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


_VARIANT_PATTERNS: dict[tuple[str, Any], re.Pattern[str]] = {
    ("protein", VariantSubType.SUBSTITUTION): _compile(
        r"\w\.(?P<ref>[A-Z]+)(?P<start>\d+)(?P<alt>[A-Z]+)"
    ),
    ("protein", VariantSubType.INSERTION): _compile(
        r"\w\.(?P<start>\d+)_(?P<end>\d+)ins(?P<alt>[A-Z]+)"
    ),
    ("protein", VariantSubType.FRAME_SHIFT): _compile(r"\w\.(?P<ref>[A-Z]+)(?P<start>\d+)fs"),
    ("protein", VariantSubType.DELETION): _compile(r"\w\.(?P<ref>[A-Z]+)(?P<pos>\d+)del"),
    ("nucleotide", VariantSubType.SUBSTITUTION): _compile(
        r"\w\.(?P<ref>[ACGTURYSWKMBDHVN]+)(?P<start>\d+)(?P<alt>[ACGTURYSWKMBDHVN]+)"
    ),
    ("nucleotide", VariantSubType.FRAME_SHIFT): _compile(
        r"\w\.(?P<ref>[ACGTURYSWKMBDHVN]+)(?P<start>\d+)fs"
    ),
    ("nucleotide", VariantSubType.DELETION): _compile(
        r"\w\.(?P<ref>[ACGTURYSWKMBDHVN]+)(?P<start>\d+)del"
    ),
    ("nucleotide", VariantSubType.DUPLICATION): _compile(
        r"\w\.(?P<ref>[ACGTURYSWKMBDHVN]+)(?P<start>\d+)dup"
    ),
    ("nucleotide", VariantSubType.INVERSION): _compile(
        r"\w\.(?P<ref>[ACGTURYSWKMBDHVN]+)(?P<start>\d+)inv"
    ),
}


class PresetName(StrEnum):
    """What the species presets are called in the output."""

    KPSC = "klebsiella_pneumo_complex"
    EC = "escherichia"


def _set_nested_iter(d: dict[str, Any], path: list[str], value: Any) -> None:
    """Iteratively set nested keys. Creates dict nodes as needed."""
    cur = d
    for key in path[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[path[-1]] = value


def _normalize_kleborate_row(row: DelimiterRow) -> DelimiterRow:
    """Wrapps normalize row."""
    normed = normalize_row(
        row,
        key_fn=lambda r: r.strip(),
        val_fn=lambda v: None if is_nullish(v) else v,
        column_map=COLUMN_MAP,
    )
    # convert flat dict to nested dict.
    header_paths = {h: h.split("__") for h in normed}

    nested: dict[str, Any] = {}
    for column, path in header_paths.items():
        value = normed[column]
        _set_nested_iter(nested, path, value)
    return nested


def _parse_qc(result: Mapping[str, Any]) -> KleborateQcResult | None:
    contig_stats = result.get("general", {}).get("contig_stats")
    if contig_stats:
        return KleborateQcResult(
            n_contigs=safe_int(contig_stats["contig_count"]),
            n50=safe_int(contig_stats["N50"]),
            largest_contig=safe_int(contig_stats["largest_contig"]),
            total_length=safe_int(contig_stats["total_size"]),
            ambigious_bases=True if contig_stats["ambiguous_bases"] == "yes" else "no",
            qc_warnings=contig_stats["QC_warnings"],
        )


def _parse_species(result: Mapping[str, Any]) -> KleboreateSppResult | None:
    """Parse species prediction results into a KleborateSpp result."""
    entb = result.get("enterobacterales")
    if not isinstance(entb, Mapping):
        return None
    raw = entb.get("species")
    if not isinstance(raw, Mapping):
        return None

    return KleboreateSppResult(
        scientific_name=raw.get("species", "unknown"),
        match=raw.get("species_match", "weak"),
    )


def _parse_virulence(result: Mapping[str, Any]) -> KleborateEtScore | None:
    """Get virulence score from result."""
    preset = result.get("klebsiella_pneumo_complex")
    if not isinstance(preset, Mapping):
        raise AbsentResultError("'klebsiella_pneumo_complex' specific analysis not in result.")

    vir = preset.get("virulence_score")
    if not isinstance(vir, Mapping):
        return None

    return KleborateEtScore(
        score=safe_int(vir.get("virulence_score")),
        spurious_hits=vir.get("spurious_virulence_hits"),
    )


def _parse_kaptive(
    result: Mapping[str, Any],
) -> dict[AnalysisType.K_TYPE, KleborateKaptiveLocus]:
    """Parse kaptive results in Kleborate and return K/O typing results."""

    # Only available for KPSC
    if (data := result.get(PresetName.KPSC)) is None:
        raise AbsentResultError("'klebsiella_pneumo_complex' specific analysis not in result.")

    def _fmt_res(d: dict[str, Any], method: Literal["K", "O"]) -> KleborateKaptiveLocus:
        return KleborateKaptiveLocus(
            locus=d[f"{method}_locus"],
            type=d[f"{method}_type"],
            identity=float(d[f"{method}_locus_identity"]),
            confidence=d[f"{method}_locus_confidence"].lower(),
            problems=d[f"{method}_locus_problems"],
            missing_genes=d[f"{method}_Missing_expected_genes"],
        )

    return {
        AnalysisType.K_TYPE: _fmt_res(data, "K"),
        AnalysisType.O_TYPE: _fmt_res(data, "O"),
    }


def _parse_mlst_like(
    result: Mapping[str, Any],
) -> dict[AnalysisType, KleborateMlstLikeResults]:
    """
    Parse the MLST-like blocks from result["klebsiella"] using your schema definitions.
    Returns mapping AnalysisType -> dict result.
    """
    out: dict[AnalysisType, dict[str, Any]] = {}

    kleb = result.get("klebsiella")
    if not isinstance(kleb, Mapping):
        raise AbsentResultError("'klebsiella_pneumo_complex' specific analysis not in result.")

    for schema_name, schema_def in _MLST_LIKE_SCHEMAS.items():
        analysis_type = _MLST_TO_ANALYSISTYPE.get(schema_name)
        if not analysis_type:
            continue

        typing_result = kleb.get(schema_name)
        if not isinstance(typing_result, Mapping):
            continue

        lineage_key: str = schema_def["lineage_key"]
        st_key: str = schema_def["st_key"]
        qc_keys: list[str] = schema_def["qc_keys"]

        if lineage_key not in typing_result or st_key not in typing_result:
            # silently skip; data not present
            continue

        lineage_val = typing_result.get(lineage_key)
        lineage = "; ".join(lineage_val) if isinstance(lineage_val, list) else lineage_val

        st_val = typing_result.get(st_key)
        sequence_type: Any
        if isinstance(st_val, str):
            try:
                sequence_type = int(st_val)
            except ValueError:
                sequence_type = st_val
        else:
            sequence_type = st_val

        skip = {lineage_key, st_key, *qc_keys}
        alleles = {k: v for k, v in typing_result.items() if k not in skip}

        out[analysis_type] = KleborateMlstLikeResults(
            scheme=schema_name,
            lineage=lineage,
            sequence_type=sequence_type,
            alleles=alleles,
        )

    return out


def _is_gene_entry(entry: HamronizationEntry) -> bool:
    """Return true if entry is a gene."""
    t = (entry.genetic_variation_type or "").lower()
    return "gene" in t


def _is_variant_entry(entry: HamronizationEntry) -> bool:
    """Return true if entry is a variant."""
    t = (entry.genetic_variation_type or "").lower()
    return ("variant" in t) or ("mutation" in t)


def _infer_variant_subtype(variant_str: str) -> VariantSubType:
    """Infer variant subtype from substring markers."""
    s = variant_str.lower()
    if "ins" in s:
        return VariantSubType.INSERTION
    if "del" in s:
        return VariantSubType.DELETION
    if "dup" in s:
        return VariantSubType.DUPLICATION
    if "inv" in s:
        return VariantSubType.INVERSION
    if "fs" in s:
        return VariantSubType.FRAME_SHIFT
    return VariantSubType.SUBSTITUTION


def _parse_variant_str(
    variant_str: str | None,
    *,
    warn: WarnFn | None = None,
    strict: bool = False,
) -> ParsedVariant | None:
    """
    Parse the HGVS-like variant string reported by Kleborate/hAMRonization.

    - Returns ParsedVariant or None if unparsable.
    - Uses `warn()` for warnings; does not depend on global LOG.
    - If strict=True, raises ValueError on unknown format.
    """
    if not variant_str:
        return None

    v = variant_str.strip()
    subtype = _infer_variant_subtype(v)

    # Determine residue type (nucleotide/protein)
    residue_type: Literal["nucleotide", "protein"]
    if v.startswith(("c.", "g.", "n.")) or (v and v[0] in ("c", "g", "n")):
        residue_type = "nucleotide"
    elif v.startswith("p."):
        residue_type = "protein"
    else:
        msg = f"Unknown variant string prefix: {variant_str!r}"
        if warn:
            warn(msg)
        if strict:
            raise ValueError(msg)
        return None

    pattern = _VARIANT_PATTERNS.get((residue_type, subtype))
    if not pattern:
        msg = f"Unsupported {residue_type} {subtype} variant: {variant_str!r}"
        if warn:
            warn(msg)
        if strict:
            raise ValueError(msg)
        return None

    m = pattern.fullmatch(v)
    if not m:
        msg = (
            f"Could not parse variant string {variant_str!r} "
            f"with pattern for {residue_type} {subtype}"
        )
        if warn:
            warn(msg)
        if strict:
            raise ValueError(msg)
        return None

    return ParsedVariant.model_validate({"residue": residue_type, "type": subtype, **m.groupdict()})


def _hamr_phenotype(record: HamronizationEntry) -> PhenotypeInfo | None:
    """Get phenotypic info from hamronization entry."""
    if record.drug_class is not None:
        return PhenotypeInfo(
            type=ElementType.AMR,
            name=record.drug_class,
            group=record.drug_class,
            annotation_type=AnnotationType.TOOL,
        )


def _parse_amr(entries: HamronizationEntries, *, warn: WarnFn) -> ElementTypeResult:
    """Convert hAMRonization results and return in a standardized format."""
    genes: list[AmrFinderResistanceGene] = []
    variants: list[AmrFinderVariant] = []

    if not entries:
        return ElementTypeResult(variants=[], genes=[])

    for row_no, entry in enumerate(entries, start=1):
        q_start = entry.input.gene_start or 0
        q_end = entry.input.gene_stop or 0
        contig = entry.input.sequence_id or entry.input.file_name
        strand = safe_strand(entry.strand_orientation)

        if _is_gene_entry(entry):
            pheno = _hamr_phenotype(entry)
            genes.append(
                AmrFinderResistanceGene(
                    gene_symbol=entry.gene_symbol,
                    sequence_name=entry.gene_name,
                    element_type=ElementType.AMR,
                    element_subtype=ElementAmrSubtype.AMR,
                    contig_id=contig,
                    query_start_pos=q_start,
                    query_end_pos=q_end,
                    strand=strand,
                    ref_start_pos=entry.reference.gene_start,
                    ref_end_pos=entry.reference.gene_stop,
                    target_length=entry.reference.gene_length,
                    method=entry.analysis_software_name or None,
                    identity=entry.sequence_identity,
                    coverage=entry.coverage_percentage,
                    phenotypes=[pheno] if pheno else [],
                )
            )
            continue

        if _is_variant_entry(entry):
            # Determine subtype/type from the HGVS-like string, if present
            pv = _parse_variant_str(
                entry.protein_mutation or entry.nucleotide_mutation,
                warn=warn,
                strict=False,  # don’t hard fail just due to variant string formatting
            )

            extra_fields: dict[str, Any] = {}
            variant_subtype = pv.type if pv else VariantType.SNV

            if pv:
                if pv.residue == "nucleotide":
                    extra_fields["ref_nt"] = getattr(pv, "ref", None)
                    extra_fields["alt_nt"] = getattr(pv, "alt", None)
                else:
                    extra_fields["ref_aa"] = getattr(pv, "ref", None)
                    extra_fields["alt_aa"] = getattr(pv, "alt", None)

            variants.append(
                AmrFinderVariant(
                    id=row_no,
                    gene_symbol=entry.gene_symbol,
                    variant_type=VariantType.INDEL,
                    variant_subtype=variant_subtype,
                    contig_id=contig,
                    query_start_pos=q_start,
                    query_end_pos=q_end,
                    start=entry.reference.gene_start or 0,
                    end=entry.reference.gene_stop or 0,
                    identity=(
                        entry.sequence_identity if entry.sequence_identity is not None else -1
                    ),
                    depth=entry.coverage_depth,
                    coverage=(
                        entry.coverage_percentage if entry.coverage_percentage is not None else -1
                    ),
                    frequency=getattr(entry, "variant_frequency", None),
                    passed_qc=None,
                    confidence=None,
                    method=entry.analysis_software_name or None,
                    strand=strand,
                    **extra_fields,
                )
            )
            continue

    return ElementTypeResult(variants=variants, genes=genes)


@register_parser(KLEBORATE)
class KleborateParser(BaseParser):
    """KleborateParser."""

    software = KLEBORATE
    parser_name = "KleborateParser"
    parser_version = 1
    schema_version = 1

    produces = {
        AnalysisType.SPECIES,
        AnalysisType.QC,
        AnalysisType.K_TYPE,
        AnalysisType.O_TYPE,
        AnalysisType.VIRULENCE,
        AnalysisType.ABST,
        AnalysisType.CBST,
        AnalysisType.RMST,
        AnalysisType.SMST,
        AnalysisType.YBST,
        AnalysisType.AMR,
    }

    mlst_family = {
        AnalysisType.ABST,
        AnalysisType.CBST,
        AnalysisType.RMST,
        AnalysisType.SMST,
        AnalysisType.YBST,
    }

    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        strict: bool = False,
        hamronization_source: StreamOrPath | None = None,
        **kwargs: Any,
    ) -> ParseImplOut:
        """Parse Kleborate TSV. Aggregates results per sample_id across all rows."""
        # Aggregate per analysis type -> sample_id -> payload

        row_iter = read_delimited(source)
        try:
            first_row = next(row_iter)
        except StopIteration:
            self.log_info(f"{self.software} input empty")
            return {atype: envelope_absent("Empty input") for atype in want}

        self.validate_columns(first_row, required=REQUIRED_COLUMNS, strict=strict)

        out: dict[AnalysisType, Any] = {}

        # convert result as nested dict
        observed_sample_ids: str | None = None
        nested = _normalize_kleborate_row(first_row)
        for raw_row in chain([first_row], row_iter):
            nested = _normalize_kleborate_row(raw_row)

            # verify that a sample not been seen before
            sample_id = nested["sample_id"]
            if observed_sample_ids is None:
                observed_sample_ids = sample_id

            if observed_sample_ids != sample_id:
                self.log_error(
                    "There are multiple sample ids in file",
                    sample_ids=[observed_sample_ids, sample_id],
                )
                raise ParserError(
                    (
                        "There are multiple sample ids in file, "
                        f"{observed_sample_ids} != {sample_id}"
                    )
                )

            base_meta = {
                "parser": self.parser_name,
                "software": self.software,
                "sample_id": sample_id,
            }
            # Species
            if AnalysisType.SPECIES in want:
                out[AnalysisType.SPECIES] = run_as_envelope(
                    analysis_name=AnalysisType.SPECIES,
                    fn=lambda: _parse_species(nested),
                    reason_if_absent="Spp results not present",
                    reason_if_empty="No species prediction",
                    meta=base_meta,
                    logger=self.logger,
                )

            if AnalysisType.QC in want:
                out[AnalysisType.QC] = run_as_envelope(
                    analysis_name=AnalysisType.QC,
                    fn=lambda: _parse_qc(nested),
                    reason_if_absent="No QC results present",
                    reason_if_empty="No QC result",
                    meta=base_meta,
                    logger=self.logger,
                )

            if AnalysisType.VIRULENCE in want:
                out[AnalysisType.VIRULENCE] = run_as_envelope(
                    analysis_name=AnalysisType.VIRULENCE,
                    fn=lambda: _parse_virulence(nested),
                    reason_if_absent="No virulence prediction in result",
                    reason_if_empty="No virulence genes",
                    meta=base_meta,
                    logger=self.logger,
                )

            # K/O types (Kaptive)
            if AnalysisType.K_TYPE in want or AnalysisType.O_TYPE in want:
                kaptive_env = run_as_envelope(
                    analysis_name="Kaptive",
                    fn=lambda: _parse_kaptive(nested),
                    reason_if_absent="Kaptive not present",
                    reason_if_empty="Kaptive result",
                    meta=base_meta,
                    logger=self.logger,
                )
                if kaptive_env.status == ResultStatus.PARSED:
                    kaptive_value: dict[AnalysisType, Any] = kaptive_env.value or {}
                    if AnalysisType.K_TYPE in want:
                        payload = kaptive_value.get(AnalysisType.K_TYPE)
                        out[AnalysisType.K_TYPE] = envelope_from_value(
                            payload, meta={**base_meta, "step": "kaptive.k_type"}
                        )
                    if AnalysisType.O_TYPE in want:
                        payload = kaptive_value.get(AnalysisType.O_TYPE)
                        out[AnalysisType.O_TYPE] = envelope_from_value(
                            payload, meta={**base_meta, "step": "kaptive.o_type"}
                        )
                else:
                    # Propagate non-PARSED status
                    # (ABSENT/EMPTY/ERROR) to requested sub-types
                    if AnalysisType.K_TYPE in want:
                        out[AnalysisType.K_TYPE] = ResultEnvelope(
                            status=kaptive_env.status,
                            reason=kaptive_env.reason,
                            meta={**kaptive_env.meta, "step": "kaptive.k_type"},
                        )
                    if AnalysisType.O_TYPE in want:
                        out[AnalysisType.O_TYPE] = ResultEnvelope(
                            status=kaptive_env.status,
                            reason=kaptive_env.reason,
                            meta={**kaptive_env.meta, "step": "kaptive.o_type"},
                        )

            # MLST-like typing (ABST/CBST/RMST/SMST/YBST)
            if self.mlst_family & want:
                mlst_env = run_as_envelope(
                    analysis_name="mlst_like",
                    fn=lambda: _parse_mlst_like(nested),
                    reason_if_absent="mlst-like block not present",
                    reason_if_empty="No predictions",
                    meta=base_meta,
                    logger=self.logger,
                )
                if mlst_env.status == ResultStatus.PARSED:
                    values: dict[AnalysisType, Any] = mlst_env.value or {}
                    for atype in self.mlst_family & want:
                        out[atype] = envelope_from_value(
                            values.get(atype),
                            meta={**base_meta, "step": f"mlst_like.{atype.value}"},
                        )
                else:
                    # Propagate shared status to the requested MLST-like outputs
                    for atype in self.mlst_family & want:
                        out[atype] = ResultEnvelope(
                            status=mlst_env.status,
                            reason=mlst_env.reason,
                            meta={**mlst_env.meta, "step": f"mlst_like.{atype.value}"},
                        )

            # Parse AMR predictions
            if AnalysisType.AMR in want:
                if hamronization_source is None:
                    m = "Cannot parse AMR since no hAMRonization results were provided."
                    self.log_error(m)
                    out[AnalysisType.AMR] = envelope_error(m, meta={**base_meta, "step": "amr"})
                else:
                    hparser = HAmrOnizationParser()
                    hres = hparser.parse(hamronization_source)

                    res = hres.results.get(AnalysisType.AMR)
                    if res.status != "parsed":
                        # Should not happen if prepopulated by that parser
                        out[AnalysisType.AMR] = envelope_absent(
                            "hAMRonization AMR not present",
                            meta={**base_meta, "step": "amr"},
                        )
                    else:
                        out[AnalysisType.AMR] = run_as_envelope(
                            analysis_name="amr_from_hamronization",
                            fn=lambda: _parse_amr(res.value, warn=self.log_warning),
                            reason_if_absent="AMR not present",
                            reason_if_empty="No AMR findings",
                            meta=base_meta,
                            logger=self.logger,
                        )
        return out
