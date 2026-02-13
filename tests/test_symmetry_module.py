"""Unit tests for the molecular symmetry helper."""

import logging
import sys
from pathlib import Path

import pytest

try:
    from astra_gui.utils.symmetry_module import Symmetry
except ModuleNotFoundError:
    SRC_PATH = Path(__file__).resolve().parents[1] / 'src'
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    from astra_gui.utils.symmetry_module import Symmetry


def test_symmetry_normalises_group_and_initialises_tables() -> None:
    """Known groups should initialise derived tables and properties."""
    symmetry = Symmetry('c2v')

    assert symmetry.group == 'C2v'
    assert symmetry.generators == ['X', 'Y']
    assert symmetry.irrep[0] == 'ALL'
    assert symmetry.dipole == ['B1', 'B2', 'A1']
    assert symmetry.mult_table[0][1] == 'B1'


def test_symmetry_invalid_group_logs_error_and_raises(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown groups should emit an error and raise when tables are requested."""
    caplog.set_level(logging.ERROR)
    with pytest.raises(KeyError):
        Symmetry('c9')
    assert 'Invalid symmetry group: C9' in caplog.text


def test_get_generators_list_reports_all_groups() -> None:
    """Generator listing should include every supported group with readable text."""
    summaries = Symmetry.get_generators_list()
    assert summaries[0] == 'C1 (no generators)'
    assert any(summary.startswith('C2v (X Y)') for summary in summaries)
    assert len(summaries) == len(Symmetry.GROUPS)


def test_get_all_symmetry_elements_combines_generators() -> None:
    """Symmetry elements are produced from generator combinations."""
    symmetry = Symmetry('C2v')
    elements = symmetry.get_all_symmetry_elements()
    assert set(elements) == {'X', 'Y', 'XY'}


def test_mult_looks_up_table_entries() -> None:
    """Irrep multiplication uses the precomputed lookup table."""
    symmetry = Symmetry('C2v')
    assert symmetry.mult('A1', 'B1') == 'B1'
    assert symmetry.mult('B2', 'B2') == 'A1'


def test_repr_and_equality_depend_on_group() -> None:
    """String representation and equality reduce to the symmetry group."""
    symmetry = Symmetry('C2v')
    duplicate = Symmetry('c2v')
    other = Symmetry('C1')

    assert repr(symmetry).startswith('Symmetry(group: C2v')
    assert symmetry == duplicate
    assert symmetry != other
    assert symmetry != object()


def test_convert_cs_irreps_to_letter_and_apostrophe_for_cs() -> None:
    """Cs labels should convert both ways between apostrophe and letter forms."""
    symmetry = Symmetry('Cs')

    assert symmetry.convert_cs_irreps_to_letter("1A',1A''") == '1Ap,1App'
    assert symmetry.convert_cs_irreps_to_apostrophe('1Ap,1App') == "1A',1A''"


def test_convert_cs_irreps_is_noop_for_non_cs_groups() -> None:
    """Conversion helpers should leave non-Cs labels untouched."""
    symmetry = Symmetry('C2v')
    text = "1A',1A'',A1,B2,1Ap,1App"

    assert symmetry.convert_cs_irreps_to_letter(text) == text
    assert symmetry.convert_cs_irreps_to_apostrophe(text) == text
