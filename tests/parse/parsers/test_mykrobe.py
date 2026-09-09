"""Test Mykrobe parser."""

from bonsai_libs.parse.models.enums import AnalysisType
from bonsai_libs.parse.models.base import ElementTypeResult, ParserOutput, ResultEnvelope
from bonsai_libs.parse.models.typing import ResultLineageBase
from bonsai_libs.parse.parsers.mykrobe import MykrobeParser


def test_mykrobe_parser_results(mtuberculosis_mykrobe_path):
    """Test Mykrobe parser"""

    parser = MykrobeParser()
    result = parser.parse(mtuberculosis_mykrobe_path)

    # test that result is method index
    assert isinstance(result, ParserOutput)

    # test that result contain the expected types
    result_types = list(result.results.keys())
    assert all(method in result_types for method in parser.produces)

    spp = result.results[AnalysisType.SPECIES]
    assert isinstance(spp, ResultEnvelope)

    # verify that species prediction was included
    assert len(spp.value) == 1
    assert spp.value[0].scientific_name == "Mycobacterium tuberculosis"

    # verify that lineage prediction
    lin = result.results["lineage"]
    assert isinstance(lin, ResultEnvelope)
    assert isinstance(lin.value, ResultLineageBase)

    # verify that amr predictions
    pred = result.results["amr"]
    assert isinstance(pred, ResultEnvelope)
    assert isinstance(pred.value, ElementTypeResult)
    assert len(pred.value.variants) == 6
