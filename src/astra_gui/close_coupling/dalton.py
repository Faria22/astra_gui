"""Notebook page that prepares Dalton input files and parses outputs."""

import logging
import re
import tkinter as tk
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, cast

from astra_gui.utils.popup_module import save_success_popup
from astra_gui.utils.required_fields_module import RequiredFields

from .cc_notebook_page_module import CcNotebookPage

if TYPE_CHECKING:
    from .create_cc_notebook import CreateCcNotebook
    from .lucia import Lucia

logger = logging.getLogger(__name__)


class Dalton(CcNotebookPage):
    """Notebook page for configuring and running Dalton calculations."""

    DALTON_FILE = Path('DALTON.INP')
    MOLECULE_FILE = Path('MOLECULE.INP')
    OUTPUT_FILE = Path('QC/DALTON.OUT')
    SCRIPT_COMMANDS = ['dalton.x']

    def __init__(self, notebook: 'CreateCcNotebook') -> None:
        super().__init__(notebook, 'Initial Orbitals')
        self.basis_reference_list = self.get_basis()

        # Basis
        self.hover_widget(ttk.Label, self, text='Basis:', hover_text='Gaussian basis used by Dalton').grid(
            row=0,
            column=0,
            pady=(15, 0),
        )
        self.basis_combo = ttk.Combobox(self, values=self.basis_reference_list)
        self.basis_combo.grid(row=0, column=1, pady=(15, 0))
        self.basis_combo.bind('<KeyRelease>', self.filter_basis_combo)
        self.basis_combo.set('6-311G')

        # Description
        self.hover_widget(
            ttk.Label,
            self,
            text='Description:',
            hover_text='Description for the current calculation',
        ).grid(row=1, column=0, padx=5, pady=5)
        self.description_entry = ttk.Entry(self)
        self.description_entry.grid(row=1, column=1)

        ttk.Label(self, text='Integral Accuracy').grid(row=2, column=0)
        self.accuracy_entry = ttk.Entry(self)
        self.accuracy_entry.grid(row=2, column=1)
        self.accuracy_entry.insert(0, '1.00D-10')

        # Occupied orbitals frame
        self.occupied_orbs_frame = ttk.Frame(self)
        self.occupied_orbs_frame.grid(row=4, column=0, columnspan=10)

        # Adds doubly/singly occupied labels and checkbuttons
        self.OCCUPIED_OPTIONS = ('doubly', 'singly')
        self.occupied_orb_vars: list[tk.BooleanVar] = []
        for occ_ind, occ_option in enumerate(self.OCCUPIED_OPTIONS, 1):
            occupied_var = tk.BooleanVar()
            self.occupied_orb_vars.append(occupied_var)
            ttk.Checkbutton(self.occupied_orbs_frame, variable=occupied_var, command=self.print_irrep).grid(
                row=occ_ind,
                column=0,
            )
            self.hover_widget(
                ttk.Label,
                self.occupied_orbs_frame,
                text=f'{occ_option.capitalize()} Occupied',
                hover_text=f'{occ_option.capitalize()} occupied orbitals',
            ).grid(row=occ_ind, column=1, padx=5)

        # Multiplicity
        self.hover_widget(
            ttk.Label,
            self,
            text='Multiplicity:',
            hover_text='Multiplicity of the state to be optimized',
        ).grid(row=5, column=0)
        self.multiplicity_entry = ttk.Entry(self)
        self.multiplicity_entry.grid(row=5, column=1)

        # Symmetry
        self.hover_widget(ttk.Label, self, text='Symmetry:', hover_text='Symmetry of the state to be optimized').grid(
            row=6,
            column=0,
        )
        self.symmetry_combo = ttk.Combobox(self, values=[])
        self.symmetry_combo.grid(row=6, column=1)

        # Number of self.electronsEntry
        ttk.Label(self, text='Number of electrons:').grid(row=7, column=0)
        self.electrons_entry = ttk.Entry(self)
        self.electrons_entry.grid(row=7, column=1)

        self.save_button.grid(row=8, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=9, column=0)

    def run(self) -> None:
        """Execute Dalton and update dependent outputs."""
        self.run_astra_setup('d', 'Dalton')
        self.get_outputs()

    def get_basis(self) -> list[str]:
        """Return the list of available Dalton basis sets.

        Returns
        -------
        list[str]
            Alphabetically sorted list of basis labels.
        """
        basis_path = self.controller.astra_gui_path / 'close_coupling' / 'basis_dalton.txt'
        with basis_path.open('r') as f:
            basis = [line.rstrip('\n') for line in f.readlines()]

        return sorted(basis)

    def filter_basis_combo(self, _event: tk.Event) -> None:
        """Filter basis combobox options based on users input."""
        current_basis: str = self.basis_combo.get()

        if not current_basis:
            self.basis_combo['values'] = self.basis_reference_list
        else:
            values = []
            for item in self.basis_reference_list:
                if item.lower().startswith(current_basis.lower()):
                    values.append(item)  # noqa: PERF401

            self.basis_combo['values'] = values

    def print_irrep(self, new_sym: bool = False) -> None:
        """Update doubly/singly orbitals to the new irreducible representation."""

        def is_new_sym_occ_orb_row_shown(ind: int) -> bool:
            """Check if the row is shown but doesn't have all the current irreps labels/entries.

            Returns
            -------
            bool
                True when the row needs to be refreshed for a new symmetry.
            """
            if not self.occupied_orb_vars[ind].get():
                return False

            # Checks if the current symmetry irreps are shown
            # by checking if the last irrep entry is shown
            return (
                self.get_widget_from_grid(
                    self.occupied_orbs_frame,
                    ind + 1,
                    len(self.sym.irrep),
                )
                is None
            )

        self.symmetry_combo['values'] = self.sym.irrep[1:]

        # Loops through the rows removes previous irreducible representations
        for row_ind in range(3):
            # Checks if the not doubly/singly occupied checkbox is checked and if "row" is the appropriate number
            if not new_sym and any(self.occupied_orb_vars[i].get() and row_ind == i + 1 for i in range(2)):
                continue

            # Destroys the irrep labels/entries if its a new sym or the occupied option is not shown
            for col in range(2, 10):
                widget = self.get_widget_from_grid(
                    self.occupied_orbs_frame,
                    row_ind,
                    col,
                )
                if widget:
                    widget.destroy()

        for i, irrep in enumerate(self.sym.irrep[1:], start=2):
            ttk.Label(self.occupied_orbs_frame, text=irrep).grid(row=0, column=i, padx=5)
            for row_ind in range(2):
                if is_new_sym_occ_orb_row_shown(row_ind):
                    ttk.Entry(self.occupied_orbs_frame, width=5).grid(row=row_ind + 1, column=i)

    def load(self) -> None:
        """Load Dalton configuration from disk and update widgets."""

        def fill_occ_orbs_entries(occupied: list[str], row: int) -> None:
            for col, occ in enumerate(occupied, start=2):
                widget = cast(ttk.Entry, self.get_widget_from_grid(self.occupied_orbs_frame, row, col))
                if widget is None:
                    raise RuntimeError('Warning: widget is None in fill_occ_orbs_entries')

                widget.delete(0, tk.END)
                widget.insert(0, occ)

        if not self.path_exists(self.DALTON_FILE):
            return

        lines = self.read_file(self.DALTON_FILE, '!')

        get_value = partial(self.get_value_from_lines, lines)

        # Pulls this info from MOLECULE.INP
        self.basis_combo.set(self.notebook.dalton_data['basis'])

        self.description_entry.delete(0, tk.END)
        self.description_entry.insert(
            0,
            str(self.notebook.dalton_data['description']),
        )

        self.accuracy_entry.delete(0, tk.END)
        self.accuracy_entry.insert(0, str(self.notebook.molecule_data['accuracy']))

        for occ_ind, occ in enumerate(self.OCCUPIED_OPTIONS):
            if occ_values := get_value(f'.{occ.upper()} OCCUPIED').split():
                if occ == 'doubly':
                    self.notebook.dalton_data['doubly_occupied'] = ' '.join(occ_values)
                self.occupied_orb_vars[occ_ind].set(True)
                self.print_irrep()
                fill_occ_orbs_entries(occ_values, occ_ind + 1)

        if multiplicity := get_value('.SPIN MULTIPLICITY'):
            self.multiplicity_entry.insert(0, multiplicity)
            self.notebook.dalton_data['multiplicity'] = int(multiplicity)

        if sym_ind := int(get_value('.SYMMETRY')):
            self.symmetry_combo.current(sym_ind - 1)
            self.notebook.dalton_data['state_sym'] = sym_ind

        if electrons := get_value('.ELECTRONS'):
            self.electrons_entry.insert(0, electrons)

        self.get_outputs()

    def get_outputs(self) -> None:
        """Update downstream pages with Dalton output data if available."""
        if not self.path_exists(self.OUTPUT_FILE):
            return

        if doubly_occupied := self.get_doubly_occ_from_output():
            self.notebook.dalton_data['doubly_occupied'] = doubly_occupied

        self.notebook.dalton_data['orbital_energies'] = self.get_orbital_energies()

        lucia_page = cast('Lucia', self.notebook.pages[2])
        lucia_page.show_dalton_output()

    def get_doubly_occ_from_output(self) -> str:
        """Extract the list of doubly occupied orbitals from the output file.

        Returns
        -------
        str
            Space-separated list of orbital labels; empty when unavailable.
        """
        lines = self.read_file(self.OUTPUT_FILE)
        for line in lines:
            if '@    Occupied SCF orbitals' in line:
                # Extract numbers after '|'
                match = re.search(r'\|\s*(.*)', line)
                if match:
                    numbers = match.group(1).split()
                    return ' '.join(numbers)
        return ''

    def get_orbital_energies(self) -> str:
        """Return the formatted orbital energies section from the output.

        Returns
        -------
        str
            Multi-line string containing the orbital energies block.
        """
        file_content = self.read_file_content(self.OUTPUT_FILE)

        # Define the pattern to match the section between two markers
        pattern = r'Sym\s+Hartree-Fock orbital energies\s+([\s\S]*?)E\(LUMO\)'

        # Find the section using the pattern
        match = re.search(pattern, file_content)
        if match:
            return match.group(1).strip()

        logger.warning('Error loading dalton output')
        return ''

    def save(self) -> None:
        """Validate entries and write updated Dalton inputs to disk."""

        def get_occ_orb_entries(ind: int) -> str:
            occupied: list[str] = []
            for col in range(2, len(self.sym.irrep) + 1):
                widget = cast(
                    ttk.Entry,
                    self.get_widget_from_grid(self.occupied_orbs_frame, ind, col),
                )
                val = widget.get()
                if not val:
                    val = '0'
                occupied.append(val)

            return ' '.join(occupied)

        # Updates molecule_data and save new MOLECULE.INP files
        self.notebook.dalton_data['basis'] = self.basis_combo.get()
        self.notebook.dalton_data['description'] = self.description_entry.get()

        self.save_file(
            self.MOLECULE_FILE,
            {**self.notebook.molecule_data, **self.notebook.dalton_data},
            '!',
            blank_lines=False,
        )

        required_fields = [
            ('symmetry', self.symmetry_combo, str),
            ('multiplicity', self.multiplicity_entry, int),
            ('electrons', self.electrons_entry, int),
        ]

        @dataclass
        class DaltonRequiredFields(RequiredFields):
            symmetry: str = ''
            multiplicity: int = 0
            electrons: int = 0

            symmetry_widget: ttk.Combobox = self.symmetry_combo
            multiplicity_widget: ttk.Entry = self.multiplicity_entry
            electrons_widget: ttk.Entry = self.electrons_entry

        required_fields = DaltonRequiredFields()

        if not required_fields.check_fields():
            return

        logger.debug(required_fields.__dict__)

        # Saving DALTON.INP
        self.notebook.dalton_data['state_sym'] = self.sym.irrep.index(required_fields.symmetry)
        self.notebook.dalton_data['multiplicity'] = required_fields.multiplicity
        self.notebook.dalton_data['electrons'] = required_fields.electrons

        for occ_ind, occ_option in enumerate(['doubly', 'singly']):
            if self.occupied_orb_vars[occ_ind].get():
                self.notebook.dalton_data[occ_option] = (
                    f'.{occ_option.upper()} OCCUPIED\n{get_occ_orb_entries(occ_ind + 1)}'
                )
            else:
                self.notebook.dalton_data[occ_option] = ''

        self.save_file(self.DALTON_FILE, self.notebook.dalton_data, '!', blank_lines=False)
        save_success_popup(f'{self.label} inputs saved successfully.')

    def erase(self) -> None:
        """Reset Dalton form fields to their defaults."""
        self.basis_combo.set('6-311G')
        self.symmetry_combo.set('')

        self.description_entry.delete(0, tk.END)
        self.accuracy_entry.delete(0, tk.END)
        self.accuracy_entry.insert(0, '1.00D-10')
        self.multiplicity_entry.delete(0, tk.END)
        self.electrons_entry.delete(0, tk.END)

        for i in range(2):
            self.occupied_orb_vars[i].set(False)

        self.print_irrep()

    def error_function(self) -> tuple[bool, str | None]:
        """Return success status and error message for Dalton runs.

        Returns
        -------
        tuple[bool, str | None]
            Success flag and optional error description.
        """
        if not self.path_exists(self.OUTPUT_FILE):
            return False, 'No output was generated.'

        if self.successful_calculation():
            return True, None

        return (
            False,
            'Dalton finished running, but did not complete full routine successfully.',
        )

    def successful_calculation(self) -> bool:
        """Return True if Dalton reports a successful calculation.

        Returns
        -------
        bool
            True when the output indicates a successful run.
        """
        content = self.read_file_content(self.OUTPUT_FILE)
        return 'Molecular wave function and energy' in content
