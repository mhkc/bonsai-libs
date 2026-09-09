"""Functions for parsing serotypefinder result."""

from typing import Any

from bonsai_libs.parse.io.delimited import is_nullish
from bonsai_libs.parse.io.json import read_json
from bonsai_libs.parse.io.types import StreamOrPath
from bonsai_libs.parse.core.base import BaseParser
from bonsai_libs.parse.models.base import ParseImplOut
from bonsai_libs.parse.core.envelope import envelope_absent, run_as_envelope
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import InvalidDataFormat, ParserError
from bonsai_libs.parse.models.base import GeneBase
from bonsai_libs.parse.models.enums import (
    AnalysisSoftware,
    AnalysisType,
    ElementSerotypeSubtype,
    ElementType,
)

from .utils import safe_int

SEROTYPEFINDER = AnalysisSoftware.SEROTYPEFINDER
ANALYSIS_TYPE_FIELDS = {
    AnalysisType.O_TYPE: "O_type",
    AnalysisType.H_TYPE: "H_type",
}


def parse_serotype_gene(
    info: dict[str, Any],
    subtype: ElementSerotypeSubtype = ElementSerotypeSubtype.ANTIGEN,
) -> GeneBase:
    """Parse serotype gene prediction results."""
    start_pos, end_pos = [safe_int(pos) for pos in info["position_in_ref"].split("..")]
    # Some genes doesnt have accession numbers
    accnr = None if is_nullish(info["accession"]) else info["accession"]
    return GeneBase(
        # info
        gene_symbol=info["gene"],
        accession=accnr,
        sequence_name=info["serotype"],
        # gene classification
        element_type=ElementType.ANTIGEN,
        element_subtype=subtype,
        # position
        ref_start_pos=start_pos,
        ref_end_pos=end_pos,
        ref_gene_length=info["template_length"],
        alignment_length=info["HSP_length"],
        # prediction
        identity=info["identity"],
        coverage=info["coverage"],
    )


def _verify_data(raw: dict[str, Any]):
    """Verify results."""
    block = raw.get("serotypefinder")
    if not isinstance(block, dict):
        raise InvalidDataFormat("Missing 'serotypefinder' block in JSON")

    results = block.get("results")
    if not isinstance(results, dict):
        raise InvalidDataFormat("Missing or malformed 'results' field.")


def pick_best_hit(hits: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the best hit from a SerotypeFinder hit dict:

    hits = {"hit1": {...}, "hit2": {...}}
    Uses identity then coverage as ranking.
    """
    if not hits:
        return None

    def score(hit: dict[str, Any]) -> tuple[float, float]:
        try:
            return (
                float(hit.get("identity") or 0.0),
                float(hit.get("coverage") or 0.0),
            )
        except (ValueError, TypeError):
            return (0.0, 0.0)

    return max(hits.values(), key=score)


def _is_no_hit(value: Any) -> bool:
    """Return true if no hit was found."""
    return isinstance(value, str) or value is None or value == {}


@register_parser(SEROTYPEFINDER)
class SerotypeFinderParser(BaseParser):
    """Parses SerotypeFinder results."""

    software = SEROTYPEFINDER
    parser_name = "SerotypeFinderParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.O_TYPE, AnalysisType.H_TYPE}

    def _parse_impl(
        self,
        source: StreamOrPath,
        *,
        want: set[AnalysisType],
        strict: bool = False,
        **_: Any,
    ) -> ParseImplOut:
        """Parse SerotypeFinder JSON."""

        # read analysis result
        try:
            pred_obj = read_json(source)
        except Exception as exc:
            self.log_error("Failed to read SerotypeFinder JSON", error=str(exc))
            if strict:
                raise
            return {}

        # verify data
        try:
            _verify_data(pred_obj)
        except ParserError as exc:
            self.log_warning(str(exc))
            return {}

        out: dict[AnalysisType, Any] = {}

        pred_res = pred_obj["serotypefinder"]["results"]

        base_meta = {"parser": self.parser_name, "software": self.software}
        # parse results
        for analysis_type in sorted(self.produces):
            if analysis_type in want:
                # get prediction result for analysis type
                hits = pred_res.get(ANALYSIS_TYPE_FIELDS[analysis_type])
                # Value might be a string if there is no hit
                if _is_no_hit(hits):
                    out[analysis_type] = envelope_absent(f"No {analysis_type} hit", meta=base_meta)
                    continue

                # verify data
                if not isinstance(hits, dict):
                    self.log_warning(
                        "Unexpected format of serotype result",
                        serotype=analysis_type,
                        got=str(type(hits)),
                    )
                    continue

                # there can be several hits for a given serotype, pick the best
                hit = pick_best_hit(hits)
                if hit is None:
                    out[analysis_type] = envelope_absent(f"No {analysis_type} hit", meta=base_meta)

                out[analysis_type] = run_as_envelope(
                    analysis_name=analysis_type,
                    fn=lambda: parse_serotype_gene(hit),
                    reason_if_absent=f"{analysis_type} not present",
                    reason_if_empty="No findings",
                    meta=base_meta,
                    logger=self.logger,
                )
        return out
