"""Kleborate specific models."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from bonsai_libs.parse.core.registry import register_result_model

from .base import RWModel
from .enums import VariantSubType, AnalysisSoftware, AnalysisType
from .typing import LineageMixin, TypingResultMlst


@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.QC)
class KleborateQcResult(BaseModel):
    """QC metrics reported by Kleborate."""

    n_contigs: int
    n50: int
    largest_contig: int
    total_length: int
    ambigious_bases: bool
    qc_warnings: None | bool = None


@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.SPECIES)
class KleboreateSppResult(RWModel):
    """Species prediction results."""

    scientific_name: str = Field(..., alias="scientificName")
    match: Literal["strong", "weak"] = Field(
        ..., description="Strength of the species call depending on the Mash distance."
    )


@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.ABST)
@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.CBST)
@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.RMST)
@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.SMST)
@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.YBST)
class KleborateMlstLikeResults(TypingResultMlst, LineageMixin):
    """Kleborate MLST-like analysis"""


@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.VIRULENCE)
class KleborateEtScore(RWModel):
    """Records and validate score."""

    score: int = Field(..., ge=0, le=5)
    spurious_hits: Any


@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.K_TYPE)
@register_result_model(AnalysisSoftware.KLEBORATE, AnalysisType.O_TYPE)
class KleborateKaptiveLocus(RWModel):
    """Kleboraete curation of Kaptive typing."""

    locus: str
    type: str
    identity: float = Field(..., ge=0, le=1)
    confidence: Literal["typeable", "untypeable"]
    problems: Any
    missing_genes: Any


class KleborateAmrPrediction(RWModel):
    """Store Kleborate AMR results."""

    score: int = Field(..., ge=0, le=6)


class ParsedVariant(BaseModel):
    """Structured output of a Kleborate HGVS-like variant string."""

    ref: str = Field(default="", min_length=0, max_length=10)
    alt: str = Field(default="", min_length=0, max_length=20)
    start: int = Field(..., ge=1)
    end: int | None = Field(default=None, ge=1)
    residue: Literal["nucleotide", "protein"]
    type: VariantSubType

    @field_validator("ref", "alt", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any):
        return v.strip() if isinstance(v, str) else v
