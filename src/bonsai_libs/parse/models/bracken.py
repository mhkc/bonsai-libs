"""Bracken specific data models."""

from typing import TypeAlias
from pydantic import Field, TypeAdapter

from bonsai_libs.parse.core.registry import register_result_model

from .base import BaseSpeciesPrediction
from .enums import TaxLevel, AnalysisSoftware, AnalysisType


class BrackenSpeciesPrediction(BaseSpeciesPrediction):
    """Species prediction results."""

    taxonomy_lvl: TaxLevel = Field(..., alias="taxLevel")
    kraken_assigned_reads: int = Field(..., alias="krakenAssignedReads")
    added_reads: int = Field(..., alias="addedReads")
    fraction_total_reads: float = Field(..., alias="fractionTotalReads")


BrackenSpeciesPredictions: TypeAlias = list[BrackenSpeciesPrediction]

register_result_model(
    AnalysisSoftware.BRACKEN,
    AnalysisType.SPECIES,
)(TypeAdapter(BrackenSpeciesPredictions))
