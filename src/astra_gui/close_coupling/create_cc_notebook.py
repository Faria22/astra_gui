"""Notebook that groups pages used to set up close-coupling calculations."""

from tkinter import ttk
from typing import TYPE_CHECKING

from astra_gui.utils.notebook_module import Notebook

from .bsplines import Bsplines
from .cc_notebook_page_module import CcNotebookPage
from .clscplng import Clscplng
from .dalton import Dalton
from .lucia import Lucia
from .molecule import Molecule

if TYPE_CHECKING:
    from astra_gui.app import Astra

    from .bsplines import BsplinesData
    from .clscplng import CcData
    from .dalton import DaltonData
    from .lucia import LuciaData
    from .molecule import MoleculeData


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

        self.add_pages([Molecule, Dalton, Lucia, Clscplng, Bsplines])
        self.reset()

    def reset(self) -> None:
        """Reset shared data structures and clear each page."""
        for page in self.pages:
            page.reset()

        self.erase()
