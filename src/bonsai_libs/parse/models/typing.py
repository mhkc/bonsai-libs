"""Chewbacca specific models."""

from typing import Any, TypeAlias

from pydantic import BaseModel, Field, TypeAdapter

from bonsai_libs.parse.core.registry import register_result_model
from .base import RWModel
from .enums import AnalysisSoftware, AnalysisType


class ResultMlstBase(BaseModel):
    """Base class for storing MLST-like typing results"""

    alleles: dict[str, int | str | list | None]


@register_result_model(AnalysisSoftware.MLST, AnalysisType.MLST)
class TypingResultMlst(ResultMlstBase):
    """MLST results"""

    scheme: str
    sequence_type: int | str | None = None


@register_result_model(AnalysisSoftware.CHEWBBACA, AnalysisType.CGMLST)
class TypingResultCgMlst(ResultMlstBase):
    """MLST results"""

    n_novel: int = 0
    n_missing: int = 0


@register_result_model(AnalysisSoftware.EMMTYPER, AnalysisType.EMM)
class TypingResultEmm(BaseModel):
    """Container for emmtype gene information"""

    cluster_count: int
    emmtype: str | None = None
    emm_like_alleles: list[str] | None = None
    emm_cluster: str | None = None


class LineageMixin(BaseModel):
    """Adds a lineage field to existing model"""

    lineage: str | None


class LineageInformation(RWModel):
    """Base class for storing lineage information typing results"""

    lineage: str | None
    family: str | None
    rd: str | None
    fraction: float | None
    support: list[dict[str, Any]] | None = None


LineageResults: TypeAlias = list[LineageInformation]
register_result_model(AnalysisSoftware.TBPROFILER, AnalysisType.LINEAGE)(
    TypeAdapter(LineageResults)
)


@register_result_model(AnalysisSoftware.MYKROBE, AnalysisType.LINEAGE)
class ResultLineageBase(RWModel):
    """Lineage results"""

    lineage_depth: float | None = None
    main_lineage: str
    sublineage: str


@register_result_model(AnalysisSoftware.SCCMECTYPER, AnalysisType.SCCMEC)
class TypingResultSccmec(RWModel):
    """Sccmec results"""

    type: str | None = None
    subtype: str | None = None
    mecA: str | None = None
    targets: list[str] | None = None
    regions: list[str] | None = None
    target_schema: str
    target_schema_version: str
    region_schema: str
    region_schema_version: str
    camlhmp_version: str
    coverage: list[float] | None = None
    hits: list[int] | None = None
    target_comment: str | None = None
    region_comment: str | None = None
    comment: str | None = None


@register_result_model(AnalysisSoftware.SPATYPER, AnalysisType.SPATYPE)
class TypingResultSpatyper(RWModel):
    """Spatyper results"""

    sequence_name: str | None
    repeats: str | None
    type: str | None


class ShigatyperHit(BaseModel):
    """A single k-mer/gene hit supporting a ShigaTyper prediction."""

    name: str
    n_reads: int


@register_result_model(AnalysisSoftware.SHIGATYPER, AnalysisType.SHIGATYPE)
class TypingResultShigatyper(RWModel):
    """ShigaTyper species/pathotype prediction results"""

    prediction: str
    ipaB: str | None = None
    notes: str | None = None
    hits: list[ShigatyperHit] = Field(default_factory=list)
