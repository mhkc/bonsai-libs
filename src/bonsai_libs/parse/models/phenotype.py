"""AMRfinder specific models."""

from pydantic import Field

from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.core.registry import register_result_element_models

from .base import DatabaseReferenceMixin, GeneBase, PhenotypeModelMixin, VariantBase
from .enums import SequenceStrand


class AmrFinderGene(GeneBase):
    """Container for Resfinder gene prediction information"""

    contig_id: str
    query_start_pos: int | None = Field(None, description="Start position on the assembly")
    query_end_pos: int | None = Field(None, description="End position on the assembly")
    strand: SequenceStrand | None


class AmrFinderResistanceGene(GeneBase, PhenotypeModelMixin):
    """For resistance predictions."""


class AmrFinderVirulenceGene(GeneBase, DatabaseReferenceMixin):
    """Container for virulence gene information"""


class AmrFinderVariant(VariantBase):
    """Container for AmrFinder variant information."""

    contig_id: str
    query_start_pos: int = Field(..., description="Alignment start in contig")
    query_end_pos: int = Field(..., description="Alignment start in contig")
    ref_gene_length: int | None = Field(
        None,
        alias="target_length",
        description="The length of the reference protein or gene.",
    )
    strand: SequenceStrand | None = None
    coverage: float
    identity: float


class TbProfilerVariant(VariantBase):
    """Container for TbProfiler variant information"""

    variant_effect: str | None = None
    hgvs_nt_change: str | None = Field(default=None, description="DNA change in HGVS format")
    hgvs_aa_change: str | None = Field(default=None, description="Protein change in HGVS format")


# ---------------------------------------------------------------------------
# Register phenotype models

register_result_element_models(
    AnalysisSoftware.AMRFINDER,
    AnalysisType.AMR,
    field_models={
        "genes": AmrFinderResistanceGene,
        "variants": AmrFinderVariant,
    },
)

register_result_element_models(
    AnalysisSoftware.AMRFINDER,
    AnalysisType.VIRULENCE,
    field_models={"genes": AmrFinderVirulenceGene},
)

register_result_element_models(
    AnalysisSoftware.TBPROFILER,
    AnalysisType.AMR,
    field_models={"variants": TbProfilerVariant},
)
