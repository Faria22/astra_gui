"""Notebook page that manages molecular geometry inputs."""

import logging
import re
import tkinter as tk
from collections import Counter
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

import numpy as np
from moldenViz import Plotter

from astra_gui.utils.font_module import title_font
from astra_gui.utils.notebook_module import NotebookPage
from astra_gui.utils.popup_module import required_field_popup
from astra_gui.utils.symmetry_module import Symmetry
from astra_gui.utils.table_module import Table

from .cc_notebook_page_module import CcNotebookPage

if TYPE_CHECKING:
    from .create_cc_notebook import CreateCcNotebook

logger = logging.getLogger(__name__)


class Molecule(CcNotebookPage):
    """Notebook page for specifying molecular geometry and symmetry."""

    MOLECULE_FILE = Path('MOLECULE.INP')

    def __init__(self, notebook: 'CreateCcNotebook') -> None:
        super().__init__(notebook, 'Molecular Geometry')

        # Geometry
        self.hover_widget(
            ttk.Label,
            self,
            text='Geometry label:',
            hover_text='Label for the geometry/calculation',
        ).grid(row=0, column=0, pady=(15, 0))
        self.geometry_entry = ttk.Entry(self)
        self.geometry_entry.grid(row=0, column=1, sticky='w', pady=(15, 0))

        # Creates some white space
        self.grid_rowconfigure(2, minsize=30)

        # Generators
        self.hover_widget(
            ttk.Label,
            self,
            text='Generators:',
            hover_text='Group symmetry of the molecule',
        ).grid(row=3, column=0)
        self.generators_ref_list = Symmetry.get_generators_list()
        self.generators_combo = ttk.Combobox(
            self,
            state='readonly',
            values=self.generators_ref_list,
        )
        self.generators_combo.current(0)
        self.generators_combo.grid(row=3, column=1)

        # Units
        self.hover_widget(
            ttk.Label,
            self,
            text='Units:',
            hover_text='Units used to parametrize the molecular geometry',
        ).grid(row=4, column=0)
        units_list = ['Angstrom', 'Bohr (atomic units)']
        self.units_combo = ttk.Combobox(self, state='readonly', values=units_list)
        self.units_combo.current(0)
        self.units_combo.grid(row=4, column=1)

        # Creates some white space
        self.grid_rowconfigure(5, minsize=30)

        # Table of atoms
        ttk.Label(self, text='List of inequivalent atoms:', font=title_font).grid(
            row=6,
            column=0,
            columnspan=2,
        )
        labels = [
            'Atomic number',
            "Atom's label",
            'x coordinate',
            'y coordinate',
            'z coordinate',
        ]
        table_frame = ttk.Frame(self)
        table_frame.grid(row=7, column=0, columnspan=10)
        self.atoms_table = Table(table_frame, labels)

        plot_molecule_button = ttk.Button(
            self,
            text='Plot molecule',
            command=self.plot_molecule,
        )
        plot_molecule_button.grid(row=8, column=0)

        self.save_button.grid(row=9, column=0, pady=self.SAVE_BUTTON_PADY)

    def get_all_atoms(self) -> tuple[list[int], np.ndarray]:
        """Return charges and coordinates for all atoms including symmetry copies.

        Returns
        -------
        tuple[list[int], np.ndarray]
            Atomic charges and 3D coordinates after symmetry expansion.
        """
        atom_charges = self.atoms_table.get()[0].astype(int)

        atom_centers = self.atoms_table.get()[2:]
        atom_centers = np.where(atom_centers, atom_centers, '0.0').T.astype(float)

        temp_atom_charges = atom_charges.tolist()
        temp_atom_centers = atom_centers.copy()

        sym = Symmetry(self.get_text_from_widget(self.generators_combo).split()[0])
        elements = sym.get_all_symmetry_elements()
        for atom_charge, atom_center in zip(atom_charges, atom_centers):
            for element in elements:
                temp_atom_center = atom_center.copy()
                if 'X' in element:
                    temp_atom_center[0] *= -1
                if 'Y' in element:
                    temp_atom_center[1] *= -1
                if 'Z' in element:
                    temp_atom_center[2] *= -1

                if not np.any(np.all(temp_atom_centers == temp_atom_center, axis=1)):
                    temp_atom_centers = np.vstack([temp_atom_centers, temp_atom_center])
                    temp_atom_charges.append(atom_charge)

        return temp_atom_charges, temp_atom_centers

    def is_molecule_linear(self) -> bool:
        """Return True when the geometry is approximately linear.

        Returns
        -------
        bool
            True if all atoms lie on the same line within tolerance.
        """
        tolerance = 1e-4

        points: np.ndarray = self.get_all_atoms()[1]
        if len(points) < 2:  # noqa: PLR2004
            return True  # Two points always define a line

        # Define the direction vector from the first two points
        direction = points[1] - points[0]
        norm = np.linalg.norm(direction)
        if norm == 0:
            raise ValueError('The first two atoms cannot be at the same position.')

        direction /= norm  # Normalize the direction vector

        # Check the distance of each subsequent point to the line
        for i in range(2, len(points)):
            # Vector from the first point to the current point
            vector = points[i] - points[0]

            # Calculate the cross product to find the perpendicular vector
            perpendicular_vector = np.cross(direction, vector)

            # Compute the distance as the magnitude of the perpendicular vector
            distance = np.linalg.norm(perpendicular_vector)

            # Check if the distance exceeds the tolerance
            if distance > tolerance:
                return False

        return True

    def load(self) -> None:
        """Load molecular information from the existing input file."""

        def get_group(generators: str) -> str:
            for gen_ref in self.generators_ref_list:
                group, gens = gen_ref.split(' ', 1)
                gens = gens[1:-1]  # Only gets the generators (removes parenthesis and group label)
                if generators == gens:
                    return group
            return 'C1'

        if not self.path_exists(self.MOLECULE_FILE):
            return

        lines = self.read_file(self.MOLECULE_FILE, '!')

        find_line_ind = partial(self.find_line_ind, lines)
        get_value = partial(self.get_value_from_lines, lines)

        if basis := get_value('BASIS'):
            self.notebook.dalton_data['basis'] = basis

        if geometry_label := get_value('Label:', shift=0).replace('Label:', '').strip():
            self.notebook.molecule_data['geom_label'] = geometry_label
            self.geometry_entry.insert(0, geometry_label)

            # Description is always below label
            description = get_value('Label:')
            if not description.startswith('Atomtypes'):
                self.notebook.dalton_data['description'] = description

        units = 'Angstrom'
        self.notebook.molecule_data['units'] = units
        if not find_line_ind(units):
            self.notebook.molecule_data['units'] = ''
            units = 'Bohr (atomic units)'

        if integrals_line := get_value('Integrals=', shift=0):
            match = re.search(r'Integrals=([0-9.ED+-]+)', integrals_line)
            if match:
                self.notebook.molecule_data['accuracy'] = match.group(1)

        num_generators = 0
        if generators_line := get_value('Generators=', shift=0):
            generators_match = re.search(r'Generators=(\d+)', generators_line)
            # Extract the number and the following values for generators
            if generators_match:
                num_generators = int(generators_match.group(1))

        generators = ''
        if num_generators > 0:
            match = re.search(
                rf'Generators=\d+\s+((?:\S+\s+){{{num_generators}}})',
                generators_line,
            )
            generators: str = ''
            if match:
                generators = match.group(1).strip()

            group = get_group(generators)
        else:
            group = self.generators_ref_list[0].split()[0]

        self.notebook.molecule_data['generators'] = f'{num_generators} {generators}'.strip()

        self.set_irrep(group)

        generators = generators or 'no generators'
        self.generators_combo.set(f'{group} ({generators})')
        self.units_combo.set(units)

        if not (atoms_line_ind := find_line_ind('Charge=')):
            return

        num_diff_atoms = int(lines[atoms_line_ind - 1].split('=')[1].split()[0].strip())
        num_atoms_list = []
        atoms_lines = lines[atoms_line_ind:]
        data = []
        for atom_type_ind in range(num_diff_atoms):
            start_line_ind = sum(num_atoms_list) + atom_type_ind
            charge_line = atoms_lines[start_line_ind].strip()
            charge = int(float(charge_line.split('=')[1].split()[0].strip()))
            num_atoms = int(charge_line.split('=')[2].strip())
            for atom_ind in range(1, num_atoms + 1):
                atom_line = atoms_lines[start_line_ind + atom_ind]
                atom_data = atom_line.split()
                data.append([
                    charge,
                    atom_data[0],
                    atom_data[1],
                    atom_data[2],
                    atom_data[3],
                ])

            num_atoms_list.append(num_atoms)

        table_data = np.array(data).T
        self.atoms_table.put(table_data)

        self.notebook.molecule_data['atoms_data'] = '\n'.join(lines[atoms_line_ind:])

        self.notebook.molecule_data['num_diff_atoms'] = num_diff_atoms
        self.notebook.molecule_data['number_atoms'] = np.shape(self.get_all_atoms()[1])[0]
        self.notebook.molecule_data['linear_molecule'] = self.is_molecule_linear()

    def save(self) -> None:
        """Persist the molecule data and update derived metadata."""
        self.notebook.molecule_data['geom_label'] = self.get_text_from_widget(
            self.geometry_entry,
        )

        molecule_group = self.get_text_from_widget(self.generators_combo).split()[0]
        self.set_irrep(molecule_group)

        self.notebook.molecule_data['generators'] = f'{len(self.sym.generators)} {" ".join(self.sym.generators)}'

        units = self.get_text_from_widget(self.units_combo)
        if units != 'Angstrom':
            units = ''

        self.notebook.molecule_data['units'] = units

        atoms_table_data = self.atoms_table.get()

        if not np.any(atoms_table_data):
            required_field_popup('atoms list')
            return

        diff_atoms_count = list(Counter(atoms_table_data[0]).values())

        self.notebook.molecule_data['num_diff_atoms'] = len(diff_atoms_count)

        # sort atoms by atomic number
        sorted_indices = np.argsort(atoms_table_data[0].astype(int))
        atoms_table_data = atoms_table_data[:, sorted_indices]

        atoms_data_string = ''
        ind = 0
        for num_atom in diff_atoms_count:
            charge = atoms_table_data[0, ind]
            atoms_data_string += f'Charge={charge} Atoms={num_atom}\n'
            for _atom in range(num_atom):
                coordinates = [atom_coordinate or '0' for atom_coordinate in atoms_table_data[2:, ind]]
                coordinates = [str(float(atom_coordinate)) for atom_coordinate in coordinates]
                atoms_data_string += ' '.join([atoms_table_data[1, ind], *coordinates]) + '\n'
                ind += 1

        self.notebook.molecule_data['atoms_data'] = atoms_data_string

        self.save_file(
            self.MOLECULE_FILE,
            {**self.notebook.molecule_data, **self.notebook.dalton_data},
            '!',
            blank_lines=False,
        )
        self.notebook.molecule_data['number_atoms'] = np.shape(self.get_all_atoms()[1])[0]
        self.notebook.molecule_data['linear_molecule'] = self.is_molecule_linear()

    def plot_molecule(self) -> None:
        """Render the molecule via Molden if the environment supports it."""
        atoms_table_data = self.atoms_table.get()

        if np.all(atoms_table_data == ''):  # noqa: PLC1901
            required_field_popup('atoms list')
            return

        atom_charges, atom_centers = self.get_all_atoms()

        atom_labels = np.array(['_'] * len(atom_charges))
        atom_inds = np.array(['_'] * len(atom_charges))

        molden_data = np.column_stack((atom_labels, atom_inds, atom_charges, atom_centers))

        molden_lines = [
            '[Atoms] Angs' if self.get_text_from_widget(self.units_combo) == 'Angstrom' else '[ATOMS] AU',
            *[' '.join(md) for md in molden_data],
            '[GTO]',
            '5D',
            '9G',
            '[MO]',
        ]

        Plotter(molden_lines, only_molecule=True, tk_root=self.controller)

    def set_irrep(self, group: str) -> None:
        """Update the symmetry group and notify the rest of the application."""
        prev_sym = self.sym

        NotebookPage.sym = Symmetry(group)

        logger.info('New symmetry group: %s', self.sym.group)

        if prev_sym != self.sym:
            self.controller.print_irrep(new_sym=True)
        else:
            self.controller.print_irrep()

    def erase(self) -> None:
        """Clear the molecule form fields."""
        self.geometry_entry.delete(0, tk.END)

        self.generators_combo.current(0)

        self.units_combo.set('Angstrom')

        self.atoms_table.erase()
        self.atoms_table.create()

    def get_outputs(self) -> None:
        """No additional outputs are produced for the molecule page."""

    def run(self) -> None:
        """No runtime step; molecule data feeds other notebooks."""

    def print_irrep(self, _new_sym: bool = False) -> None:
        """No additional UI updates required for symmetry changes."""
