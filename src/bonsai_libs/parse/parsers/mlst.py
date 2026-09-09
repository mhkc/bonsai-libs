"""Parse mlst.py results."""

from typing import Any

from bonsai_libs.parse.io.delimited import is_nullish
from bonsai_libs.parse.io.json import read_json
from bonsai_libs.parse.core.base import SingleAnalysisParser
from bonsai_libs.parse.core.registry import register_parser
from bonsai_libs.parse.exceptions import AbsentResultError
from bonsai_libs.parse.models.enums import AnalysisSoftware, AnalysisType
from bonsai_libs.parse.models.typing import TypingResultMlst

from .utils import safe_int

MLST = AnalysisSoftware.MLST
REQUIRED_FIELDS = {"alleles", "scheme", "sequence_type"}


def _process_allele_call(allele: str) -> str | list[str] | None:
    if allele.isdigit():
        result = int(allele)
    elif "," in allele:
        result = allele.split(",")
    elif "?" in allele:
        result = "partial"
    elif "~" in allele:
        result = "novel"
    elif allele == "-":
        result = None
    else:
        raise ValueError(f"MLST allele {allele} not expected format")
    return result


def _to_typing_result(data: dict[str, Any]) -> TypingResultMlst:
    """Convert raw json object to structured result."""

    st = None if is_nullish(data["sequence_type"]) else safe_int(data["sequence_type"])

    raw_alleles = data.get("alleles")
    if raw_alleles is None:
        raise AbsentResultError("No MLST typing result in file.")

    alleles = {gene: _process_allele_call(allele) for gene, allele in raw_alleles.items()}

    return TypingResultMlst(scheme=data["scheme"], sequence_type=st, alleles=alleles)


def _validate_result(data: Any) -> bool:
    """Validate MLST.py results."""
    if not isinstance(data, (list, tuple)):
        return False

    if len(data) != 1:
        return False
    return True


@register_parser(MLST)
class MlstParser(SingleAnalysisParser):
    """Parse MLST.py results."""

    software = MLST
    parser_name = "MlstParser"
    parser_version = 1
    schema_version = 1
    produces = {AnalysisType.MLST}

    def _parse_one(self, source, *, strict: bool = False, **kwargs) -> TypingResultMlst:
        """Parser implementation."""

        # read analysis result
        try:
            pred_obj = read_json(source)
        except Exception as exc:
            self.log_error("Failed to read SerotypeFinder JSON", error=str(exc))
            if strict:
                raise
            return {}

        # verify data
        _validate_result(pred_obj)
        first_entry = pred_obj[0]
        self.validate_columns(first_entry, required=REQUIRED_FIELDS)

        return _to_typing_result(first_entry)
