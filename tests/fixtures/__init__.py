"""Fixtures"""

from bonsai_libs.parse.models.hamronization import (
    HamronizationEntry,
    InputSequence,
    ReferenceSequence,
)

from .ecoli import *
from .kpneumoniae import *
from .mtuberculosis import *
from .saureus import *
from .streptococcus import *


@pytest.fixture()
def mlst_result_path_no_call(data_path: Path) -> Path:
    """Get path for mlst file where alleles was not called."""
    return data_path.joinpath("mlst.nocall.json")


@pytest.fixture()
def hamronization_entry() -> HamronizationEntry:
    inpt = InputSequence(file_name="A output file", gene_start=1, gene_stop=900)
    ref = ReferenceSequence(
        accession="ABC123",
        reference_db_id="PRPdb",
        reference_db_version="2.1.4",
        gene_start=1,
        gene_stop=900,
    )
    return HamronizationEntry(
        input=inpt,
        reference=ref,
        gene_symbol="Test1",
        gene_name="Test gene",
        genetic_variation_type="gene aquired",
        strand_orientation="+",
        drug_class="aminoglycoside antibiotic",
        analysis_software_name="PRP",
        analysis_software_version="1.2.3",
    )
