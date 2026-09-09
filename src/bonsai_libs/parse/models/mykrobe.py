"""Mykrobe specific data models."""

from typing import TypeAlias
from dataclasses import dataclass

from pydantic import Field, TypeAdapter

from bonsai_libs.parse.core.registry import register_result_model

from .base import BaseSpeciesPrediction
from .enums import AnalysisType, AnalysisSoftware


class MykrobeSpeciesPrediction(BaseSpeciesPrediction):
    """Mykrobe species prediction results."""

    phylogenetic_group: str = Field(..., description="Group with phylogenetic related species.")
    phylogenetic_group_coverage: float = Field(..., description="Kmer converage for phylo group.")
    species_coverage: float = Field(..., description="Species kmer converage.")


MykrobeSpeciesPredictions: TypeAlias = list[MykrobeSpeciesPrediction]
register_result_model(
    AnalysisSoftware.MYKROBE,
    AnalysisType.SPECIES,
)(TypeAdapter(MykrobeSpeciesPredictions))


@dataclass(frozen=True)
class SRProfile:
    """Result of validated fields."""

    susceptible: set[str]
    resistant: set[str]
