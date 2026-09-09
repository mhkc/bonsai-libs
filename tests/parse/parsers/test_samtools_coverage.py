"""Test functions for parsing SAMtools coverage results."""

from bonsai_libs.parse.models.base import ParserOutput, ResultEnvelope
from bonsai_libs.parse.models.enums import AnalysisType
from bonsai_libs.parse.models.qc import SamtoolsCoverageQcResult
from bonsai_libs.parse.parsers.samtools import SamtoolsCovParser


def test_samtools_coverage_parser(saureus_samtools_coverage_path):
    """Test parsing of SAMtools coverage result file."""

    parser = SamtoolsCovParser()
    result = parser.parse(saureus_samtools_coverage_path)

    # test that result is method index
    assert isinstance(result, ParserOutput)

    # verify that parser produces what it say it should
    assert all(at in parser.produces for at in result.results.keys())

    qc = result.results[AnalysisType.QC]
    assert isinstance(qc, ResultEnvelope)
    assert qc.status == "parsed"

    assert isinstance(qc.value, SamtoolsCoverageQcResult)

    # test parsing the output
    expected_samtools = {
        "contigs": [
            {
                "contig_name": "NC_002951.2",
                "start_pos": 1,
                "end_pos": 2809422,
                "n_reads": 175210,
                "cov_bases": 2678233,
                "coverage": 95.3304,
                "mean_depth": 186.651,
                "mean_base_quality": 22.6,
                "mean_map_quality": 57.5,
            },
            {
                "contig_name": "NC_006629.2",
                "start_pos": 1,
                "end_pos": 4440,
                "n_reads": 2012,
                "cov_bases": 4406,
                "coverage": 99.2342,
                "mean_depth": 351.234,
                "mean_base_quality": 24.7,
                "mean_map_quality": 30.7,
            },
        ]
    }
    # check if data matches
    assert expected_samtools == qc.value.model_dump()
