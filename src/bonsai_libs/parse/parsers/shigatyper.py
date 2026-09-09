"""Parse ShigaTyper results."""

from typing import Any

from bonsai_libs.parse.io.delimited import read_delimited
from bonsai_libs.parse.core.base import SingleAnalysisParser, StreamOrPath
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.typing import ShigatyperHit, TypingResultShigatyper

from .utils import safe_int

SHIGATYPER = AnalysisSoftware.SHIGATYPER

REQUIRED_COLUMNS = {"sample", "prediction", "ipaB", "notes"}

# ShigaTyper's `*-hits.tsv` is a pandas DataFrame dumped with its row index kept,
# so the first column is an unnamed index (header cell is blank: "\tHit\tNumber
# of reads"). Skip the real header and supply our own fieldnames rather than
# rely on that blank column name.
_HITS_FIELDNAMES = ["_index", "hit", "n_reads"]


def _parse_hits(source: StreamOrPath) -> list[ShigatyperHit]:
    """Parse the companion `*-hits.tsv` file into a list of hits."""
    hits: list[ShigatyperHit] = []
    for row in read_delimited(source, delimiter="\t", has_header=True, fieldnames=_HITS_FIELDNAMES):
        n_reads = safe_int(row.get("n_reads"))
        if row.get("hit") is None or n_reads is None:
            continue
        hits.append(ShigatyperHit(name=row["hit"], n_reads=n_reads))
    return hits


@register_parser(SHIGATYPER)
class ShigatyperParser(SingleAnalysisParser):
    """Parser for ShigaTyper species/pathotype prediction results."""

    software = SHIGATYPER
    parser_name = "ShigatyperParser"
    parser_version = 1
    schema_version = 1

    analysis_type = AnalysisType.SHIGATYPE
    produces = {analysis_type}

    def _parse_one(
        self,
        source: StreamOrPath,
        *,
        hits_path: StreamOrPath | None = None,
        strict_columns: bool = False,
        **kwargs: Any,
    ) -> TypingResultShigatyper | None:
        """Parse ShigaTyper's prediction TSV (+ optional companion hits TSV).

        Args:
            source: ShigaTyper's main output (sample, prediction, ipaB, notes)
            hits_path: optional companion `*-hits.tsv` file listing the k-mer/
                gene hits and read counts supporting the prediction
        """
        first = self._get_first_normalized_row(
            source,
            column_map={},
            required=REQUIRED_COLUMNS,
            strict_columns=strict_columns,
        )
        if first is None:
            return None

        hits = _parse_hits(hits_path) if hits_path is not None else []

        return TypingResultShigatyper(
            prediction=first["prediction"],
            ipaB=first.get("ipaB"),
            notes=first.get("notes"),
            hits=hits,
        )
