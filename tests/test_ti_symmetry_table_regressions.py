"""Regression tests for TI symmetry-table refresh behavior."""

import sys
from pathlib import Path
from typing import Any, cast

try:
    from astra_gui.time_independent.structural import Structural
    from astra_gui.time_independent.ti_notebook_page_module import TiNotebookPage
    from astra_gui.utils.symmetry_module import Symmetry
except ModuleNotFoundError:
    SRC_PATH = Path(__file__).resolve().parents[1] / 'src'
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    from astra_gui.time_independent.structural import Structural
    from astra_gui.time_independent.ti_notebook_page_module import TiNotebookPage
    from astra_gui.utils.symmetry_module import Symmetry


class DummyTreeview:
    """Minimal treeview double supporting insert/delete/get_children."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[Any, ...]] = {}
        self.deleted: list[str] = []
        self.headings: dict[str, str] = {}

    def get_children(self) -> tuple[str, ...]:
        """Return all current item ids.

        Returns
        -------
        tuple[str, ...]
            Item identifiers currently stored in the table.
        """
        return tuple(self.rows.keys())

    def insert(self, _parent: str, _index: str, values: tuple[Any, ...]) -> str:
        """Insert a row and return its generated item id.

        Returns
        -------
        str
            Generated row identifier.
        """
        item_id = f'i{len(self.rows)}'
        self.rows[item_id] = values
        return item_id

    def heading(self, col: str, text: str) -> None:
        """Store heading text changes."""
        self.headings[col] = text

    def delete(self, item_id: str) -> None:
        """Delete one row by item id."""
        self.deleted.append(item_id)
        self.rows.pop(item_id, None)

    def values(self) -> list[tuple[Any, ...]]:
        """Return all row values in insertion order.

        Returns
        -------
        list[tuple[Any, ...]]
            Stored row values.
        """
        return list(self.rows.values())


class DummyEntry:
    """Entry-like stub exposing only `delete`."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, Any]] = []

    def delete(self, start: int, end: Any) -> None:
        """Record deletion calls for assertions."""
        self.calls.append((start, end))


class DummyVar:
    """Variable-like stub exposing only `set`."""

    def __init__(self) -> None:
        self.value: Any = None

    def set(self, value: Any) -> None:
        """Store assigned values."""
        self.value = value


class _ConcreteTiPage(TiNotebookPage):
    """Concrete test double for exercising TiNotebookPage helper methods."""

    def left_screen_def(self) -> None:
        """No-op for tests."""

    def get_commands(self) -> str:
        """No-op for tests.

        Returns
        -------
        str
            Empty command string.
        """
        _ = self
        return ''

    def load(self) -> None:
        """No-op for tests."""

    def erase(self) -> None:
        """No-op for tests."""

    def get_outputs(self) -> None:
        """No-op for tests."""


def _make_ti_page_with_tables() -> tuple[_ConcreteTiPage, DummyTreeview, DummyTreeview, DummyTreeview]:
    """Create a TiNotebookPage object with fake treeviews.

    Returns
    -------
    tuple[_ConcreteTiPage, DummyTreeview, DummyTreeview, DummyTreeview]
        Concrete TI page plus symmetry/computed/target table doubles.
    """
    page = cast(_ConcreteTiPage, _ConcreteTiPage.__new__(_ConcreteTiPage))
    syms_tv = DummyTreeview()
    computed_syms_tv = DummyTreeview()
    target_states_tv = DummyTreeview()
    page.syms_tv = cast(Any, syms_tv)
    page.computed_syms_tv = cast(Any, computed_syms_tv)
    page.target_states_tv = cast(Any, target_states_tv)
    return page, syms_tv, computed_syms_tv, target_states_tv


def test_erase_cc_data_preserves_symmetry_table_rows() -> None:
    """Clearing CC data should not clear the static symmetry table."""
    page, syms_tv, computed_syms_tv, target_states_tv = _make_ti_page_with_tables()

    syms_tv.insert('', 'end', values=("A'",))
    syms_tv.insert('', 'end', values=("A''",))
    computed_iid = computed_syms_tv.insert('', 'end', values=('1A1',))
    target_iid = target_states_tv.insert('', 'end', values=('1', 'A1', '-1.0', '0.0'))

    TiNotebookPage.erase_cc_data(page)

    assert syms_tv.values() == [("A'",), ("A''",)]
    assert computed_syms_tv.values() == []
    assert target_states_tv.values() == []
    assert computed_syms_tv.deleted == [computed_iid]
    assert target_states_tv.deleted == [target_iid]


def test_print_irrep_populates_cs_irreps_when_new_sym() -> None:
    """`print_irrep(new_sym=True)` should display Cs irreps in the table."""
    page, syms_tv, _, _ = _make_ti_page_with_tables()
    page.sym = Symmetry('Cs')

    TiNotebookPage.print_irrep(page, new_sym=True)

    assert syms_tv.headings['Symmetry'] == 'Irreps of Cs'
    assert syms_tv.values() == [("A'",), ("A''",)]


def test_structural_erase_requests_irrep_refresh_with_new_sym() -> None:
    """Structural reset should force a symmetry-table repopulation."""
    page = cast(Structural, Structural.__new__(Structural))

    page.erase_cc_data = lambda: None

    print_irrep_calls: list[bool] = []
    page.print_irrep = lambda new_sym=False: print_irrep_calls.append(new_sym)

    page.op_ket_sym_entry = cast(Any, DummyEntry())
    page.dp_ket_sym_entry = cast(Any, DummyEntry())
    page.h_ket_sym_entry = cast(Any, DummyEntry())
    page.h_cap_entries = cast(Any, [DummyEntry(), DummyEntry()])
    page.h_ecs_entries = cast(Any, [DummyEntry(), DummyEntry()])
    page.susc_cap_entries = cast(Any, [DummyEntry(), DummyEntry()])
    page.susc_kw_entries = cast(Any, [DummyEntry(), DummyEntry(), DummyEntry(), DummyEntry()])

    page.op_vars = cast(Any, [DummyVar() for _ in range(4)])
    page.dp_vars = cast(Any, [DummyVar() for _ in range(6)])
    page.real_h_var = cast(Any, DummyVar())
    page.complex_h_var = cast(Any, DummyVar())
    page.ecs_h_var = cast(Any, DummyVar())
    page.real_susc_var = cast(Any, DummyVar())
    page.complex_susc_var = cast(Any, DummyVar())
    page.susc_dp_vars = cast(Any, [DummyVar() for _ in range(6)])

    cap_radii_calls: list[list[str]] = []

    def record_cap_radii(cap_radii: list[str]) -> None:
        cap_radii_calls.append(cap_radii)

    page.show_cap_radii = record_cap_radii

    Structural.erase(page)

    assert print_irrep_calls == [True]
    assert cap_radii_calls == [[]]
