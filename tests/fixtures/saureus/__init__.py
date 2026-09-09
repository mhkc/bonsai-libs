"""saureus input data fixutres."""

from pathlib import Path

import pytest


@pytest.fixture()
def saureus_v1_result(data_path: Path) -> Path:
    """Get path to the analysis result json."""
    return data_path.joinpath("saureus", "result_v1.json")


@pytest.fixture()
def saureus_v2_result(data_path: Path) -> Path:
    """Get path to the analysis result json."""
    return data_path.joinpath("saureus", "result_v2.json")


@pytest.fixture()
def saureus_sample_conf_path(data_path: Path) -> Path:
    """Get path for saureus sample config file"""
    return data_path.joinpath("saureus", "sample_1.cnf.yml")


@pytest.fixture()
def saureus_analysis_meta_path(data_path: Path) -> Path:
    """Get path for saureus meta file"""
    return data_path.joinpath("saureus", "analysis_meta.json")


@pytest.fixture()
def saureus_bwa_path(data_path: Path) -> Path:
    """Get path for saureus bwa qc file"""
    return data_path.joinpath("saureus", "bwa.qc")


@pytest.fixture()
def saureus_quast_path(data_path: Path) -> Path:
    """Get path for saureus quast file"""
    return data_path.joinpath("saureus", "quast.tsv")


@pytest.fixture()
def saureus_amrfinder_no_amr_path(data_path: Path) -> Path:
    """Get path for saureus amrfinder file"""
    return data_path.joinpath("saureus", "amrfinder.no_amr.tsv")


@pytest.fixture()
def saureus_amrfinder_v3_path(data_path: Path) -> Path:
    """Get path for saureus amrfinder v3-format file"""
    return data_path.joinpath("saureus", "amrfinder.v3.tsv")


@pytest.fixture()
def saureus_amrfinder_path(data_path: Path) -> Path:
    """Get path for saureus amrfinder v4-format file"""
    return data_path.joinpath("saureus", "amrfinder.v4.tsv")


@pytest.fixture()
def saureus_resfinder_path(data_path: Path) -> Path:
    """Get path for saureus resfinder file"""
    return data_path.joinpath("saureus", "resfinder.json")


@pytest.fixture()
def saureus_resfinder_meta_path(data_path: Path) -> Path:
    """Get path for saureus resfinder meta file"""
    return data_path.joinpath("saureus", "resfinder_meta.json")


@pytest.fixture()
def saureus_virulencefinder_path(data_path: Path) -> Path:
    """Get path for saureus virulencefinder file"""
    return data_path.joinpath("saureus", "virulencefinder.json")


@pytest.fixture()
def saureus_virulencefinder_meta_path(data_path: Path) -> Path:
    """Get path for saureus virulencefinder meta file"""
    return data_path.joinpath("saureus", "virulencefinder_meta.json")


@pytest.fixture()
def saureus_mlst_path(data_path: Path) -> Path:
    """Get path for saureus mlst file"""
    return data_path.joinpath("saureus", "mlst.json")


@pytest.fixture()
def saureus_chewbbaca_path(data_path: Path) -> Path:
    """Get path for saureus chewbbaca file"""
    return data_path.joinpath("saureus", "chewbbaca.out")


@pytest.fixture()
def saureus_bracken_path(data_path: Path) -> Path:
    """Get path for saureus bracken file"""
    return data_path.joinpath("saureus", "bracken.out")


@pytest.fixture()
def saureus_spatyper_path(data_path: Path) -> Path:
    """Get path for saureus spatyper file"""
    return data_path.joinpath("saureus", "spatyper.tsv")


@pytest.fixture()
def saureus_sccmec_path(data_path: Path) -> Path:
    """Get path for saureus sccmec file"""
    return data_path.joinpath("saureus", "sccmec.tsv")


@pytest.fixture()
def saureus_nanoplot_path(data_path: Path) -> Path:
    """Get path for saureus nanoplot file"""
    return data_path.joinpath("saureus", "nanoplot.txt")


@pytest.fixture()
def saureus_samtools_coverage_path(data_path: Path) -> str:
    """Get path for saureus samtools coverage file"""
    return str(data_path.joinpath("saureus", "samtools_coverage.txt"))


@pytest.fixture()
def saureus_samtools_stats_path(data_path: Path) -> Path:
    """Get path for saureus samtools stats file"""
    return data_path.joinpath("saureus", "samtools_stats.txt")


@pytest.fixture()
def saureus_samtools_bedcov_path(data_path: Path) -> Path:
    """Get path for saureus samtools bedcov file"""
    return data_path.joinpath("saureus", "samtools_bedcov.txt")
