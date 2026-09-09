"""Virulencefinder parser test suite."""

import pytest

from bonsai_libs.parse.models.base import (
    ElementTypeResult,
    ParserOutput,
    ResultEnvelope,
)
from bonsai_libs.parse.models.enums import AnalysisType
from bonsai_libs.parse.parsers.amrfinder import AmrFinderParser, AmrFinderV3Parser

EXPECTED_RESULT = [
    (
        "saureus_amrfinder_path",
        (
            8,
            3,
            (
                "beta-lactam",
                "fosfomycin",
                "methicillin",
                "quinolone",
                "tetracycline",
                "tigecycline",
            ),
        ),
    ),
    ("saureus_amrfinder_no_amr_path", (0, 0, tuple())),
]


EXPECTED_AMRFINDER_RESULT = [
    (
        "saureus_amrfinder_path",
        (
            15,  # virulence genes
            8,  # amr genes
            2,  # amr variants
            (
                "beta-lactam",
                "fosfomycin",
                "methicillin",
                "quinolone",
                "tetracycline",
                "tigecycline",
            ),
        ),
    ),
    ("saureus_amrfinder_no_amr_path", (0, 0, 0, tuple())),
]


@pytest.mark.parametrize("fixture_name,expected", EXPECTED_AMRFINDER_RESULT)
def test_amrfinder_parser_results(fixture_name, expected, request):
    """Test parsing amrfinder resistance."""
    exp_vir_genes, exp_genes, exp_variants, exp_phenotypes = expected
    filename = request.getfixturevalue(fixture_name)

    # parse result
    parser = AmrFinderParser()
    result = parser.parse(source=filename)

    # test that result is method index
    assert isinstance(result, ParserOutput)

    # test that result contain the expected types
    result_types = list(result.results.keys())
    assert all(method in result_types for method in parser.produces)

    # test that all virulence genes were parsed
    vir = result.results["virulence"]
    assert isinstance(vir, ResultEnvelope)
    assert isinstance(vir.value, ElementTypeResult)
    assert len(vir.value.genes) == exp_vir_genes

    # test that all genes, variants, and phenotypes are identified
    res = result.results["amr"]
    assert isinstance(res, ResultEnvelope)
    assert isinstance(res.value, ElementTypeResult)

    assert len(res.value.genes) == exp_genes
    assert len(res.value.variants) == exp_variants
    assert set(res.value.phenotypes["resistant"]) == set(exp_phenotypes)


def test_amrfinder_parser_filter(saureus_amrfinder_path):
    """Test that filtering of AMRfinder results works."""
    selected_result = AnalysisType.AMR
    parser = AmrFinderParser()
    result = parser.parse(saureus_amrfinder_path, want=selected_result)

    res = result.results[selected_result]
    assert res.status == "parsed"


def test_amrfinder_parser_v3_format(saureus_amrfinder_v3_path):
    """AMRFinder v3 column headers are parsed correctly."""
    parser = AmrFinderV3Parser()
    result = parser.parse(source=saureus_amrfinder_v3_path)

    assert isinstance(result, ParserOutput)
    assert all(at in result.results for at in parser.produces)

    vir = result.results[AnalysisType.VIRULENCE]
    assert isinstance(vir, ResultEnvelope)
    assert isinstance(vir.value, ElementTypeResult)
    assert len(vir.value.genes) == 14

    amr = result.results[AnalysisType.AMR]
    assert isinstance(amr, ResultEnvelope)
    assert isinstance(amr.value, ElementTypeResult)
    assert len(amr.value.genes) == 8
    assert len(amr.value.variants) == 3


def test_amrfinder_parser_v4_format(saureus_amrfinder_path):
    """AMRFinder v4 column headers are parsed correctly."""
    parser = AmrFinderParser()
    result = parser.parse(source=saureus_amrfinder_path)

    assert isinstance(result, ParserOutput)
    assert all(at in result.results for at in parser.produces)

    vir = result.results[AnalysisType.VIRULENCE]
    assert isinstance(vir, ResultEnvelope)
    assert isinstance(vir.value, ElementTypeResult)
    assert len(vir.value.genes) == 15

    amr = result.results[AnalysisType.AMR]
    assert isinstance(amr, ResultEnvelope)
    assert isinstance(amr.value, ElementTypeResult)
    assert len(amr.value.genes) == 8
    assert len(amr.value.variants) == 2


def test_amrfinder_parser_v4_stx_type_subtype(ecoli_amrfinder_v4_stx_path):
    """AMRFinder v4 rows with Subtype=STX_TYPE (stx operon calls) parse without error."""
    parser = AmrFinderParser()
    result = parser.parse(source=ecoli_amrfinder_v4_stx_path)

    assert isinstance(result, ParserOutput)

    vir = result.results[AnalysisType.VIRULENCE]
    assert isinstance(vir, ResultEnvelope)
    assert vir.status == "parsed"
    assert isinstance(vir.value, ElementTypeResult)
    assert len(vir.value.genes) == 24

    stx_genes = {gene.gene_symbol: gene for gene in vir.value.genes}
    operon = stx_genes["stx2c_operon"]
    assert operon.element_subtype == "STX_TYPE"
    assert operon.sequence_name == "stx2c operon"

    # the individual stx subunit calls still carry the plain VIRULENCE subtype
    assert stx_genes["stxA2"].element_subtype == "VIRULENCE"
    assert stx_genes["stxB2"].element_subtype == "VIRULENCE"

    amr = result.results[AnalysisType.AMR]
    assert isinstance(amr, ResultEnvelope)
    assert amr.status == "parsed"
    assert isinstance(amr.value, ElementTypeResult)
    assert len(amr.value.genes) == 4
    assert len(amr.value.variants) == 0
