"""B-spline basis notebook page module."""

import logging
import tkinter as tk
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, cast

from astra_gui.utils.font_module import bold_font
from astra_gui.utils.popup_module import (
    invalid_input_popup,
    missing_required_calculation_popup,
    missing_required_file_popup,
    required_field_popup,
    save_success_popup,
    warning_popup,
)
from astra_gui.utils.required_fields_module import RequiredFields

from .cc_notebook_page_module import CcNotebookPage
from .clscplng import Clscplng
from .dalton import Dalton

if TYPE_CHECKING:
    from astra_gui.time_independent.time_independent_notebook import TimeIndependentNotebook

    from .create_cc_notebook import CreateCcNotebook

logger = logging.getLogger(__name__)


class Bsplines(CcNotebookPage):
    """B-spline basis notebook page class."""

    BSPLINES_INPUT_FILE = Path('EXTERNAL_BASIS_BSPLINES.INP')
    SCATCI_INPUT_FILE = Path('SCATCI.INP')
    PRISM_FOLDER = Path('prism_inputs')
    PRISM_INPUTS = {
        'bspline': PRISM_FOLDER / Path('bspline.inp'),
        'grids': PRISM_FOLDER / Path('grids.inp'),
        'symmetry': PRISM_FOLDER / Path('symmetry_config.inp'),
    }
    SCRIPT_COMMANDS = [
        'scatci_integrals',
        'hybint.exe',
        'astraConvertIntegralsUKRmol',
        'astraConvertIntegralsHybInt',
    ]

    def __init__(self, notebook: 'CreateCcNotebook') -> None:
        super().__init__(notebook, 'B-spline Basis', two_screens=True)

    def left_screen_def(self) -> None:
        """Define the left screen of the B-splines notebook page."""
        int_lib_frame = ttk.Frame(self.left_screen)
        int_lib_frame.grid(row=0, column=0, columnspan=3)

        # Int Library
        ttk.Label(int_lib_frame, text='Integration library:').grid(row=0, column=0, pady=(0, 15))
        self.int_library_combo = ttk.Combobox(int_lib_frame, state='readonly', values=['PRISM', 'GBTOlib'])
        self.int_library_combo.current(0)
        self.int_library_combo.grid(row=0, column=1, sticky='w', pady=(0, 15), padx=5)

        # Inner radius
        ttk.Label(self.left_screen, text='Inner box size:').grid(row=1, column=0)
        self.inner_box_size_entry = ttk.Entry(self.left_screen, width=10)
        self.inner_box_size_entry.grid(row=1, column=1)

        # Box size
        ttk.Label(self.left_screen, text='Box size:').grid(row=2, column=0)
        self.box_size_entry = ttk.Entry(self.left_screen, width=10)
        self.box_size_entry.grid(row=2, column=1)

        # B-spline order
        ttk.Label(self.left_screen, text='B-splines order:').grid(row=3, column=0)
        self.bspline_order_entry = ttk.Entry(self.left_screen, width=10)
        self.bspline_order_entry.grid(row=3, column=1)

        # Number of b-splines
        ttk.Label(self.left_screen, text='Number of inner B-splines:').grid(row=4, column=0)
        self.num_bspline_entry = ttk.Entry(self.left_screen, width=10)
        self.num_bspline_entry.grid(row=4, column=1)

        # White space
        self.left_screen.grid_rowconfigure(5, minsize=30)

        # CAPs
        ttk.Label(self.left_screen, text='CAPs radii:').grid(row=6, column=0)
        self.cap_r1_entry = ttk.Entry(self.left_screen, width=10)
        self.cap_r2_entry = ttk.Entry(self.left_screen, width=10)
        self.cap_r1_entry.grid(row=6, column=1)
        self.cap_r2_entry.grid(row=6, column=2)

        # White space
        self.left_screen.grid_rowconfigure(7, minsize=30)

        # Mask
        ttk.Label(self.left_screen, text='Mask', font=bold_font).grid(row=8, column=0)

        # Mask radius
        ttk.Label(self.left_screen, text='Radius:').grid(row=9, column=0)
        self.mask_radius_entry = ttk.Entry(self.left_screen, width=10)
        self.mask_radius_entry.grid(row=9, column=1)

        # Mask width
        ttk.Label(self.left_screen, text='Width:').grid(row=10, column=0)
        self.mask_width_entry = ttk.Entry(self.left_screen, width=10)
        self.mask_width_entry.grid(row=10, column=1)

        self.save_button.grid(row=11, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=12, column=0)

    def right_screen_def(self) -> None:
        """Define the right screen of the B-splines notebook page."""
        ttk.Label(self.right_screen, text='Plot Basis', font=bold_font).pack()

        buttons_frame = ttk.Frame(self.right_screen)
        buttons_frame.pack()

        ttk.Label(buttons_frame, text='Plot External basis:').grid(row=0, column=0)
        self.plot_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(buttons_frame, variable=self.plot_var, command=self.show_plot_parameters).grid(row=0, column=1)

        # Plot Frame
        self.plot_frame = ttk.Frame(self.right_screen)

        # Num plot points
        ttk.Label(self.plot_frame, text='Number of plot points:').grid(row=0, column=0)
        self.num_plot_points_entry = ttk.Entry(self.plot_frame, width=10)
        self.num_plot_points_entry.grid(row=0, column=1)

        # R min/max
        ttk.Label(self.plot_frame, text='R:').grid(row=2, column=0)
        ttk.Label(self.plot_frame, text='Min').grid(row=1, column=1)
        ttk.Label(self.plot_frame, text='Max').grid(row=1, column=2)
        self.r_min_plot_entry = ttk.Entry(self.plot_frame, width=10)
        self.r_max_plot_entry = ttk.Entry(self.plot_frame, width=10)

        self.r_min_plot_entry.insert(0, '0.0')  # Default value

        self.r_min_plot_entry.grid(row=2, column=1)
        self.r_max_plot_entry.grid(row=2, column=2)

    def show_plot_parameters(self) -> None:
        """Show or hide the plot parameters frame."""
        self.erase_plot_parameters()
        if self.plot_var.get():
            self.plot_frame.pack(pady=10)
            self.r_max_plot_entry.insert(0, self.get_text_from_widget(self.box_size_entry))
        else:
            self.plot_frame.pack_forget()

    def erase_plot_parameters(self) -> None:
        """Clear entries tied to plotting configuration."""
        self.num_plot_points_entry.delete(0, tk.END)
        self.r_min_plot_entry.delete(0, tk.END)
        self.r_min_plot_entry.insert(0, '0.0')
        self.r_max_plot_entry.delete(0, tk.END)

    def erase(self) -> None:
        """Reset every widget on the notebook page."""
        self.cap_r1_entry.delete(0, tk.END)
        self.cap_r2_entry.delete(0, tk.END)
        self.mask_radius_entry.delete(0, tk.END)
        self.mask_width_entry.delete(0, tk.END)
        self.inner_box_size_entry.delete(0, tk.END)
        self.box_size_entry.delete(0, tk.END)
        self.bspline_order_entry.delete(0, tk.END)
        self.num_bspline_entry.delete(0, tk.END)
        self.erase_plot_parameters()

    def save(self, show_popup: bool = True) -> None:
        """Validate the current configuration and write all required input files."""
        # Saving EXTERNAL_BASIS_BSPLINES.INP

        @dataclass
        class BsplineRequiredFields(RequiredFields):
            box_size: float = 0
            num_bsplines: int = 0
            bspline_order: int = 0
            inner_box_size: float = 0
            mask_radius: float = 0
            mask_width: float = 0

            box_size_widget: ttk.Entry = self.box_size_entry
            num_bsplines_widget: ttk.Entry = self.num_bspline_entry
            bspline_order_widget: ttk.Entry = self.bspline_order_entry
            inner_box_size_widget: ttk.Entry = self.inner_box_size_entry
            mask_radius_widget: ttk.Entry = self.mask_radius_entry
            mask_width_widget: ttk.Entry = self.mask_width_entry

        required_fields = BsplineRequiredFields()

        if not required_fields.check_fields():
            return

        box_size = required_fields.box_size
        mask_radius = required_fields.mask_radius

        cap_radii = [self.get_text_from_widget(e) for e in [self.cap_r1_entry, self.cap_r2_entry]]
        cap_radii = [r for r in cap_radii if r]  # Removes empty strings
        try:
            cap_radii = [str(float(r)) for r in cap_radii]  # Removes empty strings
        except ValueError:
            invalid_input_popup('CAP radii must be a real number.')

        if not cap_radii:  # If both radii are empty
            required_field_popup('CAP radius')
            return

        if any(float(radius) > box_size for radius in cap_radii):
            warning_popup('CAPs radius bigger than box size.')

        if len(cap_radii) == 1:
            warning_popup(
                'Only one CAP radius provided. The second one will be set to box size + 10.',
            )
            cap_radii.append(str(box_size + 10))

        min_cap_radius = min(float(cap_radius) for cap_radius in cap_radii)

        if mask_radius >= min_cap_radius:
            warning_popup('Mask radius should be smaller than smallest CAP radius.')

        if mask_radius > box_size:
            invalid_input_popup('Mask radius bigger than box size.')
            return

        ti_notebook = cast('TimeIndependentNotebook', self.controller.notebooks[2])
        ti_notebook.show_cap_radii(cap_radii)

        commands: dict[str, str | float] = {
            'r_max': box_size,
            'cap_radii': ','.join(cap_radii),
            'mask_radius': mask_radius,
            'plot_basis': str(self.plot_var.get())[0],
            'mask_width': required_fields.mask_width,
        }

        if self.plot_var.get():

            @dataclass
            class PlotRequiredFields(RequiredFields):
                number_of_plot_points: int = 0
                r_min_plot: float = 0
                r_max_plot: float = 0

                number_of_plot_points_widget: ttk.Entry = self.num_plot_points_entry
                r_min_plot_widget: ttk.Entry = self.r_min_plot_entry
                r_max_plot_widget: ttk.Entry = self.r_max_plot_entry

            required_plot_fields = PlotRequiredFields()

            if not required_plot_fields.check_fields():
                return

            commands['n_plot'] = required_plot_fields.number_of_plot_points
            commands['r_plot_min'] = required_plot_fields.r_min_plot
            commands['r_plot_max'] = required_plot_fields.r_max_plot
        else:
            commands['n_plot'] = 0
            commands['r_plot_min'] = 0.0
            commands['r_plot_max'] = 0.0

        self.save_file(self.BSPLINES_INPUT_FILE, commands)

        # Saving SCATCI or PRISM
        lmax = cast(int, self.notebook.cc_data['lmax'])
        orbitals = cast(list[str], self.notebook.lucia_data['total_orbitals'])

        num_bsplines = required_fields.num_bsplines
        bspline_order = required_fields.bspline_order
        inner_radius = required_fields.inner_box_size

        if self.int_library_combo.get() == 'PRISM':
            self.save_file(self.ASTRA_FILE, {'int_library': 'HybridIntegrals'})
            self.mkdir(self.PRISM_FOLDER)

            # Saving bspline.inp
            self.save_file(
                self.PRISM_INPUTS['bspline'],
                {
                    'order': bspline_order,
                    'n_nodes': num_bsplines - bspline_order + 2,
                    'lmax': lmax,
                    'r_max': inner_radius,
                },
            )

            # Saving grids.inp
            num_grids = cast(int, self.notebook.molecule_data['number_atoms']) + 1
            grids = [f'{inner_radius}\n0.07'] + ['3.0\n0.015'] * (num_grids - 1)
            grids = [f'{g}\n14\n14' for g in grids]

            self.save_file(
                self.PRISM_INPUTS['grids'],
                {
                    'n_grids': num_grids,
                    'grid_list': ' '.join([str(i) for i in range(num_grids)]),
                    'grids': '\n\n'.join(grids),
                },
                '!',
            )

            # Saving grids.inp
            self.save_file(
                self.PRISM_INPUTS['symmetry'],
                {'group': self.sym.group.lower(), 'orbitals': ' '.join(orbitals)},
            )

            # Saves SCATCI.INP so astra doesn't complain later
            # TODO: remove when astra is fixed
            self.save_file(self.SCATCI_INPUT_FILE, {}, '!')
        else:
            self.save_file(self.ASTRA_FILE, {'int_library': 'GBTOlib'})
            if num_bsplines - bspline_order + 1 < lmax + 3:
                invalid_input_popup(
                    """The number of b-splines is not large enough. The following needs to be true\n
                       number of bsplines - order of bsplines + 1 > lmax + 3""",
                )
                return

            generators = self.sym.generators
            generators_str = ','.join([f"'{generator}'" for generator in generators])

            indices = ''
            for l in range(lmax + 1):
                indices += f'bspline_indices(1,{l}) = {l + 2},\n'
                indices += f'bspline_indices(2,{l}) = {num_bsplines - bspline_order + 1},\n\n'

            commands = {
                'inner_radius': inner_radius,
                'n_operators': len(generators),
                'operators': generators_str,
                'orbitals': ','.join(orbitals),
                'bspline_order': bspline_order,
                'n_bsplines': num_bsplines,
                'bspline_indices': indices,
                'lmax': lmax,
            }

            self.save_file(self.SCATCI_INPUT_FILE, commands, '!')

            if self.path_exists(self.PRISM_FOLDER):
                self.remove_path(self.PRISM_FOLDER)
        if show_popup:
            save_success_popup(f'{self.label} inputs saved successfully.')

    def load(self) -> None:
        """Populate the form from existing Astra or PRISM files."""

        def find_line_with_equal_sign_ind(
            lines: list[str],
            string: str,
        ) -> int | None:
            for ind, line in enumerate(lines):
                if string in line and '=' in line:
                    return ind
            return None

        def get_value_after_equal_from_lines(lines: list[str], string: str) -> str:
            if (ind := find_line_with_equal_sign_ind(lines, string)) is not None:
                return lines[ind].split('=')[-1].strip()
            return ''

        if not self.path_exists(self.BSPLINES_INPUT_FILE):
            return

        # Loads EXTERNAL_BASIS_BSPLINES.INP
        lines = self.read_file(self.BSPLINES_INPUT_FILE)

        get_value_after_equal = partial(get_value_after_equal_from_lines, lines)

        if r_max := get_value_after_equal('Rmax'):
            self.box_size_entry.insert(0, r_max)

        self.plot_var.set(False)
        if get_value_after_equal('PlotBasis') == 'T':
            self.plot_var.set(True)
            self.show_plot_parameters()

            if num_plot_points := get_value_after_equal('Nplot'):
                self.num_plot_points_entry.insert(0, num_plot_points)

            if r_min_plot := get_value_after_equal('RPlotMin'):
                self.r_min_plot_entry.delete(0, tk.END)
                self.r_min_plot_entry.insert(0, r_min_plot)

            if r_max_plot := get_value_after_equal('RPlotMax'):
                self.r_max_plot_entry.delete(0, tk.END)
                self.r_max_plot_entry.insert(0, r_max_plot)

        if cap_radii := get_value_after_equal('CAPRadius'):
            cap_radii_list = cap_radii.split(',')
            cap_radii_list = [r.strip() for r in cap_radii_list]

            ti_notebook = cast('TimeIndependentNotebook', self.controller.notebooks[2])
            ti_notebook.show_cap_radii(cap_radii_list)

            ti_notebook.show_cap_strengths()

        for radius, entry in zip(
            cap_radii_list,
            [self.cap_r1_entry, self.cap_r2_entry],
        ):
            entry.insert(0, radius)

        if mask_radius := get_value_after_equal('MASKRadius'):
            self.mask_radius_entry.insert(0, mask_radius)

        if mask_width := get_value_after_equal('MASKWidth'):
            self.mask_width_entry.insert(0, mask_width)

        # Loads files from prism_inputs
        if self.path_exists(self.PRISM_FOLDER):
            self.int_library_combo.current(0)

            bspline_file = self.PRISM_INPUTS['bspline']
            if not self.path_exists(bspline_file):
                return

            lines = self.read_file(bspline_file)
            get_value = partial(self.get_value_from_lines, lines)

            bspline_order = 0
            if bspline_order_str := get_value('BS_ORDER'):
                bspline_order = int(bspline_order_str)
                self.bspline_order_entry.insert(0, bspline_order_str)

            if num_nodes_str := get_value('BS_NNODS'):
                num_nodes = int(num_nodes_str)
                self.num_bspline_entry.insert(0, str(num_nodes + bspline_order - 2))

            if inner_radius := get_value('BS_GRMAX'):
                self.inner_box_size_entry.insert(0, inner_radius)

        # Loads SCATCI.INP
        elif self.path_exists(self.SCATCI_INPUT_FILE):
            self.int_library_combo.current(1)

            lines = self.read_file(self.SCATCI_INPUT_FILE, '!')
            get_value_from_lines = partial(get_value_after_equal_from_lines, lines)

            if inner_radius := get_value_from_lines('a'):
                inner_radius = inner_radius.split(',')[0].strip()
                self.inner_box_size_entry.insert(0, inner_radius)

            bspline_order = 0
            if bspline_order_str := get_value_from_lines('bspline_order'):
                bspline_order = int(bspline_order_str)
                self.bspline_order_entry.insert(0, bspline_order_str)

            if num_bspline_str := get_value_from_lines('no_bsplines'):
                self.num_bspline_entry.insert(0, num_bspline_str)

    def run(self) -> None:
        """Run the close-coupling integrals pipeline when prerequisites exist."""
        if not self.path_exists(Clscplng.CLSCPLNG_FILE):
            missing_required_file_popup(str(Clscplng.CLSCPLNG_FILE))
            return

        if not self.path_exists(Dalton.OUTPUT_FILE):
            missing_required_calculation_popup('Dalton')
            return

        self.run_astra_setup('iI', 'Integrals')

    def print_irrep(self, _new_sym: bool = False) -> None:
        """Print current irreducible representations to the UI."""

    def get_outputs(self) -> None:
        """Refresh the outputs displayed by the notebook page."""
