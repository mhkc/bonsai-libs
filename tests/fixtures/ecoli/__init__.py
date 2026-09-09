"""Ecoli input data fixutres."""

from pathlib import Path

import pytest


@pytest.fixture()
def ecoli_sample_conf_path(data_path: Path) -> Path:
    """Get path for ecoli sample config file"""
    return data_path.joinpath("ecoli", "sample_1.cnf.yml")


@pytest.fixture()
def ecoli_analysis_meta_path(data_path: Path) -> Path:
    """Get path for ecoli meta file"""
    return data_path.joinpath("ecoli", "analysis_meta.json")


@pytest.fixture()
def ecoli_bwa_path(data_path: Path) -> Path:
    """Get path for ecoli bwa qc file"""
    return data_path.joinpath("ecoli", "bwa.qc")


@pytest.fixture()
def ecoli_quast_path(data_path: Path) -> Path:
    """Get path for ecoli quast file"""
    return data_path.joinpath("ecoli", "quast.tsv")


@pytest.fixture()
def ecoli_gambitcore_path(data_path: Path) -> Path:
    """Get path for ecoli gambit file"""
    return data_path.joinpath("ecoli", "gambitcore.tsv")


@pytest.fixture()
def ecoli_amrfinder_path(data_path: Path) -> Path:
    """Get path for ecoli amrfinder file"""
    return data_path.joinpath("ecoli", "amrfinder.out")


@pytest.fixture()
def ecoli_amrfinder_v4_stx_path(data_path: Path) -> Path:
    """Get path for ecoli amrfinder v4 file containing an STX_TYPE (stx operon) hit"""
    return data_path.joinpath("ecoli", "amrfinder.v4.stx.tsv")


@pytest.fixture()
def ecoli_resfinder_path(data_path: Path) -> Path:
    """Get path for ecoli resfinder file"""
    return data_path.joinpath("ecoli", "resfinder.json")


@pytest.fixture()
def ecoli_resfinder_meta_path(data_path: Path) -> Path:
    """Get path for ecoli resfinder meta file"""
    return data_path.joinpath("ecoli", "resfinder_meta.json")


@pytest.fixture()
def ecoli_virulencefinder_wo_stx_path(data_path: Path) -> Path:
    """Get path for ecoli virulencefinder without stx file"""
    return data_path.joinpath("ecoli", "virulencefinder.json")


@pytest.fixture()
def ecoli_virulencefinder_stx_pred_stx_path(data_path: Path) -> Path:
    """Get path for ecoli stx prediction file"""
    return data_path.joinpath("ecoli", "virulencefinder.stx_pred.stx.json")


@pytest.fixture()
def ecoli_virulencefinder_stx_pred_no_stx_path(data_path: Path) -> Path:
    """Get path for ecoli stx prediction no stx file"""
    return data_path.joinpath("ecoli", "virulencefinder.stx_pred.no_stx.json")


@pytest.fixture()
def ecoli_virulencefinder_meta_path(data_path: Path) -> Path:
    """Get path for ecoli virulencefinder meta file"""
    return data_path.joinpath("ecoli", "virulencefinder_meta.json")


@pytest.fixture()
def ecoli_serotypefinder_path(data_path: Path) -> Path:
    """Get path for ecoli stx prediction file"""
    return data_path.joinpath("ecoli", "serotypefinder.json")


@pytest.fixture()
def ecoli_serotypefinder_meta_path(data_path: Path) -> Path:
    """Get path for ecoli serotypefinder meta file"""
    return data_path.joinpath("ecoli", "serotypefinder_meta.json")


@pytest.fixture()
def ecoli_mlst_path(data_path: Path) -> Path:
    """Get path for ecoli mlst file"""
    return data_path.joinpath("ecoli", "mlst.json")


@pytest.fixture()
def ecoli_chewbbaca_path(data_path: Path) -> Path:
    """Get path for ecoli chewbbaca file"""
    return data_path.joinpath("ecoli", "chewbbaca.out")


@pytest.fixture()
def ecoli_bracken_path(data_path: Path) -> Path:
    """Get path for ecoli bracken file"""
    return data_path.joinpath("ecoli", "bracken.out")


@pytest.fixture()
def ecoli_shigatyper_path(data_path: Path) -> Path:
    """Get path for ecoli shigatyper file"""
    return data_path.joinpath("ecoli", "shigatyper.tsv")


@pytest.fixture()
def ecoli_shigatyper_hits_path(data_path: Path) -> Path:
    """Get path for ecoli shigatyper hits file"""
    return data_path.joinpath("ecoli", "shigatyper-hits.tsv")


@pytest.fixture()
def ecoli_kleborate_path(data_path: Path) -> Path:
    """Get path for kleborate result file"""
    return data_path.joinpath("ecoli", "kleborate_v3_escherichia_output.txt")
