"""Test bracken parser."""

import pytest

from bonsai_libs.parse.models.base import ParserOutput, ResultEnvelope
from bonsai_libs.parse.models.bracken import BrackenSpeciesPrediction
from bonsai_libs.parse.models.enums import TaxLevel, AnalysisType
from bonsai_libs.parse.parsers.bracken import BrackenParser, to_taxlevel

EXPECTED_PARSER_RESULT = [
    ("saureus_bracken_path", (None, 55)),
    ("saureus_bracken_path", (0.0001, 23)),
    ("saureus_bracken_path", (0.9, 1)),
]


@pytest.mark.parametrize("fixture_name,expected", EXPECTED_PARSER_RESULT)
def test_bracken_cutoff(fixture_name, expected, request):
    """Test bracken parser and its cutoff"""
    cutoff, n_hits = expected
    filename = request.getfixturevalue(fixture_name)
    parser = BrackenParser()

    result = parser.parse(filename, cutoff=cutoff)

    # assert correct ouptut data model
    assert isinstance(result, ParserOutput)

    spp = result.results[AnalysisType.SPECIES]
    assert isinstance(spp, ResultEnvelope)

    assert spp.status == "parsed"

    assert isinstance(spp.value[0], BrackenSpeciesPrediction)

    # test that we got the expected number of hits given the cutoff
    assert len(spp.value) == n_hits


@pytest.mark.parametrize("raw_tax_level,exp_level", [("S", TaxLevel.S), ("g", TaxLevel.G)])
def test_to_taxlevel(raw_tax_level, exp_level):
    """Test converting taxonomy level to TaxLevel enum."""

    assert to_taxlevel(raw_tax_level) == exp_level
