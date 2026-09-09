"""Parse Mykrobe results."""

import logging
import re
from dataclasses import asdict
from typing import Any, Callable, TypeAlias

from bonsai_libs.parse.io.delimited import (
    DelimiterRow,
    canonical_header,
    is_nullish,
    normalize_row,
    read_delimited,
)
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import run_as_envelope
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.base import (
    ElementTypeResult,
    PhenotypeInfo,
    SoupVersion,
    VariantBase,
)
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    AnnotationType,
    ElementType,
    SoupType,
    VariantSubType,
    VariantType,
)
from bonsai_libs.parse.models.mykrobe import (
    MykrobeSpeciesPredictions,
    MykrobeSpeciesPrediction,
    SRProfile,
)
from bonsai_libs.parse.models.typing import ResultLineageBase

from .utils import get_nt_change, safe_float, safe_int

LOG = logging.getLogger(__name__)

MYKROBE = AnalysisSoftware.MYKROBE
DELIMITER = ","

# Mykrobe AMR variant format:
# <gene>_<aa change>-<nt change>:<ref depth>:<alt depth>:<gt confidence>
VARIANT_RE = re.compile(
    r"(?P<gene>.+)_(?P<aa_change>.+)-(?P<dna_change>.+):"
    r"(?P<ref_depth>\d+):(?P<alt_depth>\d+):(?P<conf>\d+)$",
    re.IGNORECASE,
)

REQUIRED_COLUMNS = {
    "sample",
    "mykrobe_version",
    "drug",
    "susceptibility",
    "genotype_model",
    "variants",
    "species",
    "species_per_covg",
    "phylo_group",
    "phylo_group_per_covg",
    "lineage",
}


TableRows: TypeAlias = list[DelimiterRow]


def _sr_profile(rows: TableRows) -> SRProfile:
    """List antibiotics the sample is susceptible or resistant to."""
    susceptible: set[str] = set()
    resistant: set[str] = set()

    for row in rows:
        sus = (row.get("susceptibility") or "").upper()
        drug = row.get("drug")
        if not drug:
            continue
        if sus == "R":
            resistant.add(drug)
        elif sus == "S":
            susceptible.add(drug)

    return SRProfile(susceptible=sorted(susceptible), resistant=sorted(resistant))


def parse_mutation_nom(var_nom: str) -> dict[str, Any] | None:
    """
    Parse mutation token like GCG7569GTG -> ref=GCG pos=7569 alt=GTG
    Returns dict with keys: type, subtype, ref, alt, pos
    """
    if not var_nom:
        return None

    m1 = re.search(r"\d", var_nom)
    m2 = re.search(r"\d(?=[^\d]*$)", var_nom)
    if not m1 or not m2:
        return None

    ref_idx = m1.start()
    alt_idx = m2.start() + 1

    ref = var_nom[:ref_idx]
    alt = var_nom[alt_idx:]
    try:
        pos = safe_int(var_nom[ref_idx:alt_idx])
    except ValueError:
        return None

    var_len = abs(len(ref) - len(alt))
    if var_len >= 50:
        var_type = VariantType.SV
    elif 1 < var_len < 50:
        var_type = VariantType.INDEL
    else:
        var_type = VariantType.SNV

    if len(ref) > len(alt):
        subtype = VariantSubType.DELETION
    elif len(ref) < len(alt):
        subtype = VariantSubType.INSERTION
    else:
        subtype = VariantSubType.SUBSTITUTION

    return {"type": var_type, "subtype": subtype, "ref": ref, "alt": alt, "pos": pos}


def _parse_amr_variants(rows: TableRows, *, log_warning) -> list[VariantBase]:
    """Parse resistance variants."""

    out: list[VariantBase] = []
    for row_no, row in enumerate(rows, start=1):
        if (row.get("susceptibility") or "").upper() != "R":
            continue

        variants_field = row.get("variants")
        if not variants_field:
            continue

        drug = row.get("drug")
        if not drug:
            # A resistant row without a drug label is suspicious
            log_warning("Mykrobe resistant row missing drug", row=row_no)
            continue

        phenotype = [
            PhenotypeInfo(
                name=drug,
                type=ElementType.AMR,
                annotation_type=AnnotationType.TOOL,
                annotation_author=MYKROBE,
            )
        ]

        # expand variant info
        tokens = [t for t in str(variants_field).split(";") if t.strip()]
        for var_id, token in enumerate(tokens, start=1):
            match = VARIANT_RE.match(token)
            if not match:
                log_warning("Bad variant token in Mykrobe result", row=row_no, token=token)
                continue

            gd = match.groupdict()

            aa = parse_mutation_nom(gd["aa_change"])
            dna = parse_mutation_nom(gd["dna_change"])
            if aa is None or dna is None:
                log_warning(
                    "Mykrobe cannot parse mutation nomenclature",
                    row=row_no,
                    token=token,
                )
                continue

            ref_depth = safe_int(gd["ref_depth"])
            alt_depth = safe_int(gd["alt_depth"])
            denom = ref_depth + alt_depth
            freq = (alt_depth / denom) if denom else None  # avoid zero division

            ref_nt, alt_nt = dna["ref"], dna["alt"]
            if aa["subtype"] == VariantSubType.SUBSTITUTION:
                ref_nt, alt_nt = get_nt_change(ref_nt, alt_nt)

            has_aa = len(aa["ref"]) == 1 and len(aa["alt"]) == 1

            out.append(
                VariantBase(
                    id=var_id,
                    variant_type=aa["type"],
                    variant_subtype=aa["subtype"],
                    phenotypes=phenotype,
                    reference_sequence=gd["gene"],
                    start=dna["pos"],
                    end=dna["pos"] + max(len(alt_nt), 1),
                    ref_nt=ref_nt,
                    alt_nt=alt_nt,
                    ref_aa=aa["ref"] if has_aa else None,
                    alt_aa=aa["alt"] if has_aa else None,
                    method=row.get("genotype_model"),
                    depth=denom,
                    frequency=freq,
                    confidence=safe_int(gd["conf"]),
                    passed_qc=True,
                )
            )

    out.sort(key=lambda v: (v.reference_sequence or "", v.start or 0))
    return out


def _parse_species(rows: TableRows) -> MykrobeSpeciesPredictions:
    """Parse Mykrobe species predictions."""
    if not rows:
        return []

    r0 = rows[0]
    # Split fields; pad to avoid index errors if lists differ in length
    species = _split_csv_list("species", row=r0)
    phylo_groups = _split_csv_list("phylo_group", row=r0)
    phylo_covg = _split_csv_list("phylo_group_per_covg", row=r0)
    species_covg = _split_csv_list("species_per_covg", row=r0)

    out: MykrobeSpeciesPredictions = []
    for idx, spp in enumerate(species):
        if not spp.strip():
            continue

        phylo = phylo_groups[idx].replace("_", " ") if phylo_groups[idx] else None
        out.append(
            MykrobeSpeciesPrediction(
                scientific_name=spp.replace("_", " "),
                taxonomy_id=None,
                phylogenetic_group=phylo,
                phylogenetic_group_coverage=safe_float(phylo_covg[idx]) or None,
                species_coverage=safe_float(species_covg[idx]) or None,
            )
        )
    return out


def _split_csv_list(field_name: str, *, row: dict[str, Any]) -> list[str]:
    """Split csv list; pad to avoid index errors in lists differ in length."""
    return str(row.get(field_name) or "").split(";") if row.get(field_name) else []


def _parse_lineage(rows: TableRows) -> ResultLineageBase | None:
    """Parse Mykrobe lineage predictions."""
    if not rows:
        return None

    lineage = rows[0].get("lineage")
    if not lineage:
        return None

    lineage = str(lineage)
    return ResultLineageBase(
        main_lineage=lineage.split(".", maxsplit=1)[0],
        sublineage=lineage,
    )


def _normalize_mykrobe_row(row: DelimiterRow) -> DelimiterRow:
    """Wrapper for normalize rows."""
    return normalize_row(
        row,
        key_fn=canonical_header,
        val_fn=lambda v: None if is_nullish(v) else v,
    )


def _parse_amr_result(
    rows: list[DelimiterRow], *, log_fn: Callable[[Any], None]
) -> ElementTypeResult:
    """Parse AMR result."""

    phenos = _sr_profile(rows)
    variants = _parse_amr_variants(rows, log_warning=log_fn)
    return ElementTypeResult(phenotypes=asdict(phenos), genes=[], variants=variants)


@register_parser(MYKROBE)
class MykrobeParser(BaseParser):
    software = MYKROBE
    parser_name = "MykrobeParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.SPECIES, AnalysisType.AMR, AnalysisType.LINEAGE}

    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        strict_columns: bool = False,
        sample_id: str | None = None,
        **_: Any,
    ) -> ParseImplOut:
        """Core parser implementation."""

        # Read rows
        rows_iter = read_delimited(source, delimiter=DELIMITER)

        try:
            first_row = next(rows_iter)
        except StopIteration:
            self.log_info("Mykrobe input is empty")

        first_row = _normalize_mykrobe_row(first_row)
        self.validate_columns(first_row, required=REQUIRED_COLUMNS, strict=strict_columns)

        rows = [first_row] + [_normalize_mykrobe_row(r) for r in rows_iter]

        # optional sample id filter
        if sample_id is not None:
            rows = [r for r in rows if r.get("sample") == sample_id]
            if len(rows) == 0:
                self.log_warning("Sample Id not in Mykrobe result", sample_id=sample_id)
                raise ValueError("Sample id is not in Mykrobe result.")
            self.log_info(
                f"There are {len(rows)} Mykrobe prediction results are filtering",
                sample_id=sample_id,
            )

        results: dict[AnalysisType, Any] = {}

        base_meta = {
            "parser": self.parser_name,
            "software": self.software,
            "sample_id": sample_id,
        }
        if AnalysisType.AMR in want:
            at = AnalysisType.AMR
            env = run_as_envelope(
                analysis_name=at,
                fn=lambda: _parse_amr_result(rows, log_fn=self.log_warning),
                reason_if_absent=f"{at} not present",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )
            results[at] = env

        if AnalysisType.SPECIES in want:
            env = run_as_envelope(
                analysis_name=at,
                fn=lambda: _parse_species(rows),
                reason_if_absent=f"{at} not present",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )
            results[AnalysisType.SPECIES] = env

        if AnalysisType.LINEAGE in want:
            env = run_as_envelope(
                analysis_name=at,
                fn=lambda: _parse_lineage(rows),
                reason_if_absent=f"{at} not present",
                reason_if_empty="No findings",
                meta=base_meta,
                logger=self.logger,
            )
            results[AnalysisType.LINEAGE] = env

        return results

    def get_version(self, source: StreamOrPath) -> SoupVersion | None:
        """Get version of Mykrobe from result."""
        rows_iter = read_delimited(source, delimiter=DELIMITER)
        try:
            first = next(rows_iter)
        except StopIteration:
            self.log_info("Mykrobe input is empty")
            return None

        return SoupVersion(
            name=self.software,
            version=first[0]["mykrobe_version"],
            type=SoupType.DB,
        )
