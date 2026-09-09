"""Parse kraken results."""

from typing import Any

from bonsai_libs.parse.io.delimited import read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import ParserError
from bonsai_libs.parse.models.bracken import BrackenSpeciesPrediction, BrackenSpeciesPredictions
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType, TaxLevel

from .utils import safe_float, safe_int

BRACKEN = AnalysisSoftware.BRACKEN
REQUIRED_COLUMNS = {
    "name",
    "taxonomy_id",
    "taxonomy_lvl",
    "kraken_assigned_reads",
    "added_reads",
    "new_est_reads",
    "fraction_total_reads",
}


def to_taxlevel(lvl: str | TaxLevel) -> TaxLevel:
    if isinstance(lvl, TaxLevel):
        return lvl

    lvl = lvl.strip()
    if not lvl:
        raise ValueError("Empty taxonomic level")

    # 1) Try as enum NAME (e.g. "S", "G")
    try:
        return TaxLevel[lvl.upper()]
    except KeyError:
        pass

    # 2) Try as enum VALUE (e.g. "species", "genus")
    try:
        return TaxLevel(lvl.lower())
    except ValueError as exc:
        raise ValueError(f"Unknown taxonomic level: {lvl!r}") from exc


@register_parser(BRACKEN)
class BrackenParser(SingleAnalysisParser):
    """Parser for Bracken results."""

    software = BRACKEN
    parser_name = "BrackenParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.SPECIES}
    analysis_type = AnalysisType.SPECIES

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        cutoff: float | None = None,
        strict_columns: bool = False,
        **_,
    ) -> BrackenSpeciesPredictions:
        """Parse Bracken results."""
        rows = read_delimited(source)
        try:
            first_row = next(rows)
        except StopIteration:
            self.log_info("Bracken input is empty")
            return {AnalysisType.SPECIES: []}

        # Validate the columns in the first row
        self.validate_columns(first_row, required=REQUIRED_COLUMNS, strict=strict_columns)

        results: BrackenSpeciesPredictions = []
        # append first row
        if spp_obj := self._to_spp_results(first_row, cutoff=cutoff):
            results.append(spp_obj)

        for row in rows:
            spp_obj = self._to_spp_results(row, cutoff=cutoff)
            if spp_obj is not None:
                results.append(spp_obj)

        return results

    def _to_spp_results(
        self, row: dict[str, Any], *, cutoff: float | None = None
    ) -> BrackenSpeciesPrediction | None:
        """Convert row to Species prediction result"""

        try:
            raw_frac = row["fraction_total_reads"]
            frac = float(raw_frac)
        except (TypeError, ValueError) as exc:
            raise ParserError(
                f"Invalid fraction_total_reads, fraction_total_reads={raw_frac}"
            ) from exc

        if cutoff is not None and frac < cutoff:
            return

        tax_level = to_taxlevel(row["taxonomy_lvl"])
        return BrackenSpeciesPrediction(
            scientific_name=row["name"],
            taxonomy_id=row["taxonomy_id"],
            taxonomy_lvl=tax_level,
            kraken_assigned_reads=safe_int(row["kraken_assigned_reads"], logger=self.logger),
            added_reads=safe_int(row["added_reads"], logger=self.logger),
            fraction_total_reads=safe_float(row["fraction_total_reads"], logger=self.logger),
        )
