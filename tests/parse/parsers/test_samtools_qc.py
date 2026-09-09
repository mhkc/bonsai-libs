"""Test SamtoolsQcParser."""

from pathlib import Path

import pytest

from bonsai_libs.parse.models.base import ParserOutput, ResultEnvelope
from bonsai_libs.parse.models.enums import AnalysisType
from bonsai_libs.parse.models.qc import PostAlignQcResult
from bonsai_libs.parse.parsers.post_align_qc import SamtoolsQcParser


def test_samtools_qc_parser(
    saureus_samtools_stats_path: Path,
    saureus_samtools_bedcov_path: Path,
):
    """Full parse: stats + bedcov produces all metrics."""
    parser = SamtoolsQcParser()
    result = parser.parse(
        saureus_samtools_stats_path,
        bedcov_path=saureus_samtools_bedcov_path,
    )

    assert isinstance(result, ParserOutput)
    assert all(at in parser.produces for at in result.results)

    env = result.results[AnalysisType.QC]
    assert isinstance(env, ResultEnvelope)
    assert env.status == "parsed"

    qc = env.value
    assert isinstance(qc, PostAlignQcResult)

    # read counts
    assert qc.n_reads == 38702
    assert qc.n_read_pairs == 38702
    assert qc.n_mapped_reads == 38702
    assert qc.n_dup_reads == 0
    assert qc.dup_pct == pytest.approx(0.0)

    # insert size
    assert qc.ins_size == pytest.approx(498.6, rel=1e-3)
    assert qc.ins_size_dev == pytest.approx(48.1, rel=1e-3)

    # coverage metrics
    assert qc.mean_cov == pytest.approx(2.062, rel=1e-2)
    assert qc.median_cov == 2.0
    assert qc.quartile1 == 1.0
    assert qc.quartile3 == 3.0
    assert qc.coverage_uniformity == pytest.approx(1.0)

    # pct_above_x
    assert qc.pct_above_x is not None
    assert qc.pct_above_x["1"] == pytest.approx(87.3, rel=1e-2)
    assert qc.pct_above_x["10"] < 1.0
    assert qc.pct_above_x["30"] == pytest.approx(0.0, abs=1e-3)


def test_samtools_qc_parser_bedcov_as_stream(
    saureus_samtools_stats_path: Path,
    saureus_samtools_bedcov_path: Path,
):
    """bedcov_path also accepts an open text stream, not just a path."""
    parser = SamtoolsQcParser()
    with open(saureus_samtools_bedcov_path, encoding="utf-8") as bedcov_stream:
        result = parser.parse(
            saureus_samtools_stats_path,
            bedcov_path=bedcov_stream,
        )

    qc = result.results[AnalysisType.QC].value
    assert isinstance(qc, PostAlignQcResult)
    assert qc.mean_cov == pytest.approx(2.062, rel=1e-2)
    assert qc.median_cov == 2.0


def test_samtools_qc_parser_no_bedcov(saureus_samtools_stats_path: Path):
    """Without bedcov, read-level metrics are populated; coverage metrics are None."""
    parser = SamtoolsQcParser()
    result = parser.parse(saureus_samtools_stats_path)

    qc = result.results[AnalysisType.QC].value
    assert isinstance(qc, PostAlignQcResult)

    # read metrics still available
    assert qc.n_reads == 38702
    assert qc.n_read_pairs == 38702
    assert qc.ins_size == pytest.approx(498.6, rel=1e-3)

    # coverage metrics unavailable without genome length
    assert qc.mean_cov is None
    assert qc.pct_above_x is None
    assert qc.quartile1 is None
    assert qc.median_cov is None
    assert qc.quartile3 is None
    assert qc.coverage_uniformity is None
