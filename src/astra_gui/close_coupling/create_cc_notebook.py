"""Notebook that groups pages used to set up close-coupling calculations."""

from tkinter import ttk
from typing import TYPE_CHECKING, TypedDict

from astra_gui.utils.notebook_module import Notebook

from .bsplines import Bsplines
from .cc_notebook_page_module import CcNotebookPage
from .clscplng import Clscplng
from .dalton import Dalton
from .lucia import Lucia
from .molecule import Molecule

if TYPE_CHECKING:
    from astra_gui.app import Astra


class MoleculeData(TypedDict):
    """Shared molecular metadata tracked across close-coupling pages."""

    accuracy: str
    units: str
    number_atoms: int
    linear_molecule: bool
    generators: str
    geom_label: str
    atoms_data: str
    num_diff_atoms: int


class DaltonData(TypedDict):
    """State propagated between Dalton configuration steps and outputs."""

    basis: str
    description: str
    doubly_occupied: str
    orbital_energies: str
    state_sym: int
    multiplicity: int
    electrons: int
    doubly: str
    singly: str


class LuciaData(TypedDict):
    """Aggregated Lucia calculation configuration and results."""

    lcsblk: int
    electrons: int
    total_orbitals: list[str]
    states: list[str]
    energies: list[str]
    relative_energies: list[str]


class CcData(TypedDict):
    """Close-coupling metadata shared with downstream notebooks."""

    lmax: int
    total_syms: list[str]


class BsplinesData(TypedDict):
    """B-splines geometry values shared with other notebooks."""

    cap_radii: list[float]
    mask_radius: float
    mask_width: float
    box_size: float
    is_valid: bool


class CreateCcNotebook(Notebook[CcNotebookPage]):
    """Top-level notebook that walks the user through CC preparation steps."""

    def __init__(self, parent: ttk.Frame, controller: 'Astra') -> None:
        """Initialise the notebook and load all close-coupling pages."""
        super().__init__(parent, controller, 'Create Close Coupling')

        self.molecule_data: MoleculeData
        self.dalton_data: DaltonData
        self.lucia_data: LuciaData
        self.cc_data: CcData
        self.bsplines_data: BsplinesData

        # Some pages access shared data while being constructed.
        self._init_all_shared_data()
        self.add_pages([Molecule, Dalton, Lucia, Clscplng, Bsplines])
        self.erase()

    def _init_molecule_data(self) -> None:
        """Initialise shared molecule data."""
        self.molecule_data = {
            'accuracy': '1.00D-10',
            'units': 'Angstrom',
            'number_atoms': 0,
            'linear_molecule': False,
            'generators': '',
            'geom_label': '',
            'atoms_data': '',
            'num_diff_atoms': 0,
        }

    def _init_dalton_data(self) -> None:
        """Initialise shared Dalton data."""
        self.dalton_data = {
            'basis': '6-311G',
            'description': '',
            'doubly_occupied': '',
            'orbital_energies': '',
            'state_sym': 0,
            'multiplicity': 0,
            'electrons': 0,
            'doubly': '',
            'singly': '',
        }

    def _init_lucia_data(self) -> None:
        """Initialise shared Lucia data."""
        self.lucia_data = {
            'lcsblk': 106968,
            'electrons': 0,
            'total_orbitals': [],
            'states': [],
            'energies': [],
            'relative_energies': [],
        }

    def _init_cc_data(self) -> None:
        """Initialise shared close-coupling data."""
        self.cc_data = {
            'lmax': 3,
            'total_syms': [],
        }

    def _init_bsplines_data(self) -> None:
        """Initialise shared B-splines data."""
        self.bsplines_data = {
            'cap_radii': [],
            'mask_radius': 0.0,
            'mask_width': 0.0,
            'box_size': 0.0,
            'is_valid': False,
        }

    def init_bsplines_data(self) -> None:
        """Initialise only the shared B-splines data."""
        self._init_bsplines_data()

    def _init_all_shared_data(self) -> None:
        """Initialise all shared close-coupling data."""
        self._init_molecule_data()
        self._init_dalton_data()
        self._init_lucia_data()
        self._init_cc_data()
        self._init_bsplines_data()

    def erase(self) -> None:
        """Reset shared data and clear all close-coupling pages."""
        self._init_all_shared_data()
        super().erase()

    def reset(self) -> None:
        """Compatibility wrapper required by the base notebook contract."""
        self.erase()
