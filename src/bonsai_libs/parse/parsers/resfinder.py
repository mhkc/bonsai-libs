"""Parse resfinder results."""

import logging
from itertools import chain
from typing import Any

from bonsai_libs.parse.io.json import read_json, require_mapping
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import run_as_envelope
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import InvalidDataFormat
from bonsai_libs.parse.models.base import (
    ElementTypeResult,
    GeneBase,
    PhenotypeInfo,
    VariantBase,
)
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    AnnotationType,
    ElementAmrSubtype,
    ElementStressSubtype,
    ElementType,
    VariantSubType,
    VariantType,
)

from .utils import get_nt_change

LOG = logging.getLogger(__name__)

RESFINDER = AnalysisSoftware.RESFINDER

STRESS_FACTORS = {
    ElementStressSubtype.BIOCIDE: [
        "formaldehyde",
        "benzylkonium chloride",
        "ethidium bromide",
        "chlorhexidine",
        "cetylpyridinium chloride",
        "hydrogen peroxide",
    ],
    ElementStressSubtype.HEAT: ["temperature"],
}


def lookup_antibiotic_class(antibiotic: str) -> str:
    """Lookup antibiotic class for antibiotic name.

    Antibiotic classes are sourced from resfinder db v2.2.1
    """
    lookup_table = {
        "unknown aminocyclitol": "aminocyclitol",
        "spectinomycin": "aminocyclitol",
        "unknown aminoglycoside": "aminoglycoside",
        "gentamicin": "aminoglycoside",
        "gentamicin c": "aminoglycoside",
        "tobramycin": "aminoglycoside",
        "streptomycin": "aminoglycoside",
        "amikacin": "aminoglycoside",
        "kanamycin": "aminoglycoside",
        "kanamycin a": "aminoglycoside",
        "neomycin": "aminoglycoside",
        "paromomycin": "aminoglycoside",
        "kasugamycin": "aminoglycoside",
        "g418": "aminoglycoside",
        "capreomycin": "aminoglycoside",
        "isepamicin": "aminoglycoside",
        "dibekacin": "aminoglycoside",
        "lividomycin": "aminoglycoside",
        "ribostamycin": "aminoglycoside",
        "butiromycin": "aminoglycoside",
        "butirosin": "aminoglycoside",
        "hygromycin": "aminoglycoside",
        "netilmicin": "aminoglycoside",
        "apramycin": "aminoglycoside",
        "sisomicin": "aminoglycoside",
        "arbekacin": "aminoglycoside",
        "astromicin": "aminoglycoside",
        "fortimicin": "aminoglycoside",
        "unknown analog of d-alanine": "analog of d-alanine",
        "d-cycloserine": "analog of d-alanine",
        "unknown beta-lactam": "beta-lactam",
        "amoxicillin": "beta-lactam",
        "amoxicillin+clavulanic acid": "beta-lactam",
        "ampicillin": "beta-lactam",
        "ampicillin+clavulanic acid": "beta-lactam",
        "aztreonam": "beta-lactam",
        "cefazolin": "beta-lactam",
        "cefepime": "beta-lactam",
        "cefixime": "beta-lactam",
        "cefotaxime": "beta-lactam",
        "cefotaxime+clavulanic acid": "beta-lactam",
        "cefoxitin": "beta-lactam",
        "ceftaroline": "beta-lactam",
        "ceftazidime": "beta-lactam",
        "ceftazidime+avibactam": "beta-lactam",
        "ceftriaxone": "beta-lactam",
        "cefuroxime": "beta-lactam",
        "cephalothin": "beta-lactam",
        "ertapenem": "beta-lactam",
        "imipenem": "beta-lactam",
        "meropenem": "beta-lactam",
        "penicillin": "beta-lactam",
        "piperacillin": "beta-lactam",
        "piperacillin+tazobactam": "beta-lactam",
        "temocillin": "beta-lactam",
        "ticarcillin": "beta-lactam",
        "ticarcillin+clavulanic acid": "beta-lactam",
        "cephalotin": "beta-lactam",
        "piperacillin+clavulanic acid": "beta-lactam",
        "unknown diarylquinoline": "diarylquinoline",
        "bedaquiline": "diarylquinoline",
        "unknown quinolone": "quinolone",
        "ciprofloxacin": "quinolone",
        "nalidixic acid": "quinolone",
        "fluoroquinolone": "quinolone",
        "unknown folate pathway antagonist": "folate pathway antagonist",
        "sulfamethoxazole": "folate pathway antagonist",
        "trimethoprim": "folate pathway antagonist",
        "unknown fosfomycin": "fosfomycin",
        "fosfomycin": "fosfomycin",
        "unknown glycopeptide": "glycopeptide",
        "vancomycin": "glycopeptide",
        "teicoplanin": "glycopeptide",
        "bleomycin": "glycopeptide",
        "unknown ionophores": "ionophores",
        "narasin": "ionophores",
        "salinomycin": "ionophores",
        "maduramicin": "ionophores",
        "unknown iminophenazine": "iminophenazine",
        "clofazimine": "iminophenazine",
        "unknown isonicotinic acid hydrazide": "isonicotinic acid hydrazide",
        "isoniazid": "isonicotinic acid hydrazide",
        "unknown lincosamide": "lincosamide",
        "lincomycin": "lincosamide",
        "clindamycin": "lincosamide",
        "unknown macrolide": "macrolide",
        "carbomycin": "macrolide",
        "azithromycin": "macrolide",
        "oleandomycin": "macrolide",
        "spiramycin": "macrolide",
        "tylosin": "macrolide",
        "telithromycin": "macrolide",
        "erythromycin": "macrolide",
        "unknown nitroimidazole": "nitroimidazole",
        "metronidazole": "nitroimidazole",
        "unknown oxazolidinone": "oxazolidinone",
        "linezolid": "oxazolidinone",
        "unknown amphenicol": "amphenicol",
        "chloramphenicol": "amphenicol",
        "florfenicol": "amphenicol",
        "unknown pleuromutilin": "pleuromutilin",
        "tiamulin": "pleuromutilin",
        "unknown polymyxin": "polymyxin",
        "colistin": "polymyxin",
        "unknown pseudomonic acid": "pseudomonic acid",
        "mupirocin": "pseudomonic acid",
        "unknown rifamycin": "rifamycin",
        "rifampicin": "rifamycin",
        "unknown salicylic acid - anti-folate": "salicylic acid - anti-folate",
        "para-aminosalicyclic acid": "salicylic acid - anti-folate",
        "unknown steroid antibacterial": "steroid antibacterial",
        "fusidic acid": "steroid antibacterial",
        "unknown streptogramin a": "streptogramin a",
        "dalfopristin": "streptogramin a",
        "pristinamycin iia": "streptogramin a",
        "virginiamycin m": "streptogramin a",
        "quinupristin+dalfopristin": "streptogramin a",
        "unknown streptogramin b": "streptogramin b",
        "quinupristin": "streptogramin b",
        "pristinamycin ia": "streptogramin b",
        "virginiamycin s": "streptogramin b",
        "unknown synthetic" "derivative of nicotinamide": "synthetic derivative" " of nicotinamide",
        "pyrazinamide": "synthetic derivative of nicotinamide",
        "unknown tetracycline": "tetracycline",
        "tetracycline": "tetracycline",
        "doxycycline": "tetracycline",
        "minocycline": "tetracycline",
        "tigecycline": "tetracycline",
        "unknown thioamide": "thioamide",
        "ethionamide": "thioamide",
        "unknown unspecified": "unspecified",
        "ethambutol": "unspecified",
        "cephalosporins": "under_development",
        "carbapenem": "under_development",
        "norfloxacin": "under_development",
        "ceftiofur": "under_development",
    }
    return lookup_table.get(antibiotic, "unknown")


def assign_res_subtype(prediction: dict[str, Any], element_type: ElementType) -> Any:
    """Assign resistance subtype based on prediction info and element type."""

    if element_type == ElementType.STRESS:
        predicted = set(prediction.get("phenotypes") or [])
        for sub_type, phenos in STRESS_FACTORS.items():
            if set(phenos) & predicted:
                return sub_type
        return None
    if element_type == ElementType.AMR:
        return ElementAmrSubtype.AMR
    return None


def get_resfinder_sr_profile(
    resfinder_result: dict[str, Any], limit_to: list[str] | None = None
) -> dict[str, list[str]]:
    """Get resfinder susceptibility/resistance profile."""

    susceptible: set[str] = set()
    resistant: set[str] = set()

    for pheno in (resfinder_result.get("phenotypes") or {}).values():
        key = pheno.get("key")
        if limit_to is not None and key not in limit_to:
            continue

        if pheno.get("amr_resistant") is True:
            resistant.add(pheno.get("amr_resistance"))
        elif pheno.get("amr_resistant") is False:
            susceptible.add(pheno.get("amr_resistance"))

    return {
        "susceptible": sorted(x for x in susceptible if x),
        "resistant": sorted(x for x in resistant if x),
    }


def parse_resfinder_genes(
    resfinder_result: dict[str, Any], limit_to: list[str] | None = None
) -> list[GeneBase]:
    """Parse resfinder gene predictions."""

    results: list[GeneBase] = []
    phenotypes = resfinder_result.get("phenotypes") or {}
    for info in (resfinder_result.get("seq_regions") or {}).values():
        ref_db = (info.get("ref_database") or [""])[0]
        if not str(ref_db).startswith("Res"):
            continue

        if limit_to is not None:
            if not (set(info.get("phenotypes") or []) & set(limit_to)):
                continue

        # infer category from first phenotype
        phenolist = info.get("phenotypes") or []
        if not phenolist:
            continue

        first_key = phenolist[0]
        cat = phenotypes.get(first_key, {}).get("category")
        if not cat:
            continue

        res_category = ElementType(str(cat).upper())
        subtype = assign_res_subtype(info, res_category)

        phenotype_objs = [
            PhenotypeInfo(
                type=res_category,
                name=phe,
                group=lookup_antibiotic_class(phe),
                annotation_type=AnnotationType.TOOL,
                annotation_author=AnalysisSoftware.RESFINDER,
                reference=info.get("pmids"),
            )
            for phe in phenolist
        ]

        results.append(
            GeneBase(
                gene_symbol=info["name"],
                accession=info.get("ref_acc"),
                element_type=res_category,
                element_subtype=subtype,
                phenotypes=phenotype_objs,
                ref_start_pos=info["ref_start_pos"],
                ref_end_pos=info["ref_end_pos"],
                ref_gene_length=info["ref_seq_length"],
                alignment_length=info["alignment_length"],
                depth=info.get("depth"),
                identity=info["identity"],
                coverage=info["coverage"],
            )
        )

    results.sort(
        key=lambda g: (
            g.gene_symbol or "",
            g.coverage if g.coverage is not None else -1.0,
        )
    )
    return results


def parse_resfinder_variants(
    resfinder_result: dict[str, Any], limit_to: list[str] | None = None
) -> list[VariantBase]:
    """Parse resfinder variant predictions."""

    prediction_method = None
    for exec_info in (resfinder_result.get("software_executions") or {}).values():
        prediction_method = exec_info.get("parameters", {}).get("method")

    seq_regions = resfinder_result.get("seq_regions") or {}
    results: list[VariantBase] = []

    for var_id, info in enumerate((resfinder_result.get("seq_variations") or {}).values(), start=1):
        phenos = info.get("phenotypes") or []
        if limit_to is not None and not (set(phenos) & set(limit_to)):
            continue

        # compute depth without mutating info
        depth = 0
        sr_keys = info.get("seq_regions") or []
        if sr_keys and sr_keys[0] in seq_regions:
            depth = seq_regions[sr_keys[0]].get("depth", 0)

        # subtype classifier
        if info.get("substitution"):
            var_sub_type = VariantSubType.SUBSTITUTION
        elif info.get("insertion"):
            var_sub_type = VariantSubType.INSERTION
        elif info.get("deletion"):
            var_sub_type = VariantSubType.DELETION
        else:
            raise ValueError("ResFinder output has no known mutation type")

        # seq_regions[0] format: gene;;something;;acc
        gene_symbol, _, gene_accnr = sr_keys[0].split(";;")

        ref_nt, alt_nt = get_nt_change(info["ref_codon"], info["var_codon"])
        phenotype_objs = [
            PhenotypeInfo(
                type=ElementType.AMR,
                group=lookup_antibiotic_class(phe),
                name=phe,
                annotation_type=AnnotationType.TOOL,
            )
            for phe in phenos
        ]

        results.append(
            VariantBase(
                id=var_id,
                variant_type=VariantType.SNV,
                variant_subtype=var_sub_type,
                phenotypes=phenotype_objs,
                reference_sequence=gene_symbol,
                accession=gene_accnr,
                start=info["ref_start_pos"],
                end=info["ref_end_pos"],
                ref_nt=ref_nt,
                alt_nt=alt_nt,
                ref_aa=info.get("ref_aa"),
                alt_aa=info.get("var_aa"),
                depth=depth,
                method=prediction_method,
                passed_qc=True,
            )
        )

    results.sort(key=lambda v: (v.reference_sequence or "", v.start or 0))
    return results


def get_resfinder_amr_sr_profie(resfinder_result, limit_to_phenotypes=None):
    """Get resfinder susceptibility/resistance profile."""
    susceptible = set()
    resistant = set()
    for phenotype in resfinder_result["phenotypes"].values():
        # skip phenotype if its not part of the desired category
        if limit_to_phenotypes is not None and phenotype["key"] not in limit_to_phenotypes:
            continue

        if "amr_resistant" in phenotype.keys():
            if phenotype["amr_resistant"]:
                resistant.add(phenotype["amr_resistance"])
            else:
                susceptible.add(phenotype["amr_resistance"])
    return {"susceptible": list(susceptible), "resistant": list(resistant)}


def build_resfinder_result(
    pred: dict[str, Any], resistance_category: ElementType
) -> ElementTypeResult:
    """Build resfinder result for a given resistance category."""
    stress_factors = list(chain(*STRESS_FACTORS.values()))
    all_phenos = pred.get("phenotypes") or {}

    # keys used in filtering are phenotype["key"] values
    predicted_keys = list(all_phenos.keys())
    categories = {
        AnalysisType.STRESS: stress_factors,
        AnalysisType.AMR: list(set(predicted_keys) - set(stress_factors)),
    }

    limit = categories[resistance_category]
    sr_profile = get_resfinder_sr_profile(pred, limit_to=limit)
    genes = parse_resfinder_genes(pred, limit_to=limit)
    variants = parse_resfinder_variants(pred, limit_to=limit)

    return ElementTypeResult(phenotypes=sr_profile, genes=genes, variants=variants)


@register_parser(RESFINDER)
class ResFinderParser(BaseParser):
    """Parse resfinder results."""

    software = RESFINDER
    parser_name = "ResFinderParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.AMR, AnalysisType.STRESS}

    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        strict: bool = False,
        **kwargs: Any,
    ) -> ParseImplOut:
        try:
            pred = read_json(source)
            pred = require_mapping(pred, what="<root>")
            # Basic structure check: phenotypes + at least one of seq_regions/seq_variations
            if "phenotypes" not in pred:
                raise InvalidDataFormat("ResFinder JSON missing 'phenotypes'")
        except Exception as exc:
            self.log_error("Failed to read/validate ResFinder JSON", error=str(exc))
            if strict:
                raise
            return {}

        out: dict[AnalysisType, Any] = {}

        base_meta = {"parser": self.parser_name, "software": self.software}
        # AMR
        # AMR & STRESS share the same underlying element type filter in this outpu
        for analysis_type in [AnalysisType.AMR, AnalysisType.STRESS]:
            if analysis_type in want:
                out[analysis_type] = run_as_envelope(
                    analysis_name=analysis_type,
                    fn=lambda: build_resfinder_result(pred, analysis_type),
                    reason_if_absent="No resistance determinants for sample",
                    reason_if_empty="No findings",
                    meta=base_meta,
                    logger=self.logger,
                )
        return out
