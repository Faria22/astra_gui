"""Regression tests covering Lucia target-state serialisation."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import numpy as np

from tests.dummy_table import DummyTable

# Lucia depends on the optional moulden visualiser; provide a lightweight stub.
stub_module = ModuleType('moldenViz')
cast(Any, stub_module).Plotter = None
sys.modules.setdefault('moldenViz', stub_module)


try:
    from astra_gui.close_coupling.lucia import Lucia
except ModuleNotFoundError:
    SRC_PATH = Path(__file__).resolve().parents[1] / 'src'
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    from astra_gui.close_coupling.lucia import Lucia


def test_get_states_data_serialises_numeric_fields() -> None:
    """Numeric symmetry codes should be coerced to strings during save."""
    lucia = Lucia.__new__(Lucia)
    lucia.sym = cast(Any, SimpleNamespace(irrep=['ALL', 'A1']))
    lucia.notebook = cast(Any, SimpleNamespace(lucia_data={}))

    states_table = DummyTable(num_cols=3)
    table_data = np.array(
        [
            ['A1'],
            [1],
            [1],
        ],
        dtype=object,
    )
    states_table.put(table_data)

    lucia.states_table = cast(Any, states_table)
    lucia.unpack_all_sym = Lucia.unpack_all_sym.__get__(lucia, Lucia)

    _, serialized = lucia.get_states_data()

    assert serialized == '1\n1 1 1'


def test_lucia_title_filled() -> None:
    """The Lucia title property should return the correct string."""
    lucia = Lucia.__new__(Lucia)
    lucia.notebook = cast(Any, SimpleNamespace(molecule_data={}, dalton_data={}))

    lucia.notebook.molecule_data['geom_label'] = 'geom'
    lucia.notebook.dalton_data['basis'] = 'basis'
    lucia.notebook.dalton_data['description'] = 'desc'

    assert lucia.get_title() == 'geom\nbasis\ndesc'


def test_lucia_title_empty() -> None:
    """The Lucia title property should return the correct string."""
    lucia = Lucia.__new__(Lucia)
    lucia.notebook = cast(Any, SimpleNamespace(molecule_data={}, dalton_data={}))

    lucia.notebook.molecule_data['geom_label'] = ''
    lucia.notebook.dalton_data['basis'] = ''
    lucia.notebook.dalton_data['description'] = ''

    assert lucia.get_title() == 'geometry\nbasis\ndescription'
