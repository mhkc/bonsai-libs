"""Test parsing of TbProfiler results."""

from bonsai_libs.parse.models.base import ElementTypeResult, ParserOutput, ResultEnvelope
from bonsai_libs.parse.models.enums import AnalysisType
from bonsai_libs.parse.models.typing import LineageInformation
from bonsai_libs.parse.parsers.tbprofiler import TbProfilerParser


def test_tbprofier_parser_results(mtuberculosis_tbprofiler_path):
    """Test that the TbProfilerParser produces the expected result and data types."""

    parser = TbProfilerParser()
    result = parser.parse(mtuberculosis_tbprofiler_path)

    # test that result is method index
    assert isinstance(result, ParserOutput)

    # verify that parser produces what it say it should
    assert all(at in parser.produces for at in result.results.keys())

    res = result.results[AnalysisType.AMR]
    assert isinstance(res, ResultEnvelope)
    assert res.status == "parsed"

    # test parser results
    assert isinstance(res.value, ElementTypeResult)

    res = result.results[AnalysisType.LINEAGE]
    assert isinstance(res, ResultEnvelope)
    assert res.status == "parsed"

    assert isinstance(res.value, list)
    assert isinstance(res.value[0], LineageInformation)
