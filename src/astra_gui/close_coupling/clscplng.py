"""Close-coupling configuration page and supporting widgets."""

import logging
import re
import tkinter as tk
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, TypedDict, cast

import numpy as np

from astra_gui.utils.constants import AU_TO_EV, EV_TO_AU
from astra_gui.utils.font_module import title_font
from astra_gui.utils.popup_module import (
    invalid_input_popup,
    missing_required_calculation_popup,
    required_field_popup,
    save_success_popup,
)
from astra_gui.utils.required_fields_module import RequiredFields
from astra_gui.utils.scrollable_module import ScrollableFrame

from .cc_notebook_page_module import CcNotebookPage

if TYPE_CHECKING:
    from astra_gui.time_independent.time_independent_notebook import TimeIndependentNotebook

    from .bsplines import Bsplines
    from .create_cc_notebook import CreateCcNotebook

logger = logging.getLogger(__name__)


class CcData(TypedDict):
    """Close-coupling metadata shared with downstream notebooks."""

    lmax: int
    total_syms: list[str]


class Clscplng(CcNotebookPage):
    """Notebook page that manages close-coupling calculations."""

    CLSCPLNG_FILE = Path('CLSCPLNG.INP')
    SCRIPT_COMMANDS = ['astraConvertDensityMatrices']

    def reset(self) -> None:
        """Reset shared close-coupling data defaults."""
        self.notebook.cc_data = {
            'lmax': 3,
            'total_syms': [],
        }

    def __init__(self, notebook: 'CreateCcNotebook') -> None:
        """Initialise the page and prepare the layout."""
        super().__init__(notebook, 'Close Coupling', two_screens=True)

    def left_screen_def(self) -> None:
        """Populate widgets displayed on the left-hand pane."""
        ttk.Label(self.left_screen, text='Full basis:').grid(row=0, column=0, padx=5, pady=5)
        self.full_basis_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.left_screen, variable=self.full_basis_var, command=self.show_cc_list).grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
        )

        # L max
        ttk.Label(self.left_screen, text='Lmax:').grid(row=1, column=0, padx=5, pady=5)
        self.lmax_entry = ttk.Entry(self.left_screen)
        self.lmax_entry.grid(row=1, column=1, padx=5, pady=5)

        # Ion charge
        ttk.Label(self.left_screen, text='Target state charge:').grid(row=2, column=0, padx=5, pady=5)
        self.charge_entry = ttk.Entry(self.left_screen)
        self.charge_entry.grid(row=2, column=1, padx=5, pady=5)

        # CC Basis
        self.cc_basis_label = ttk.Label(self.left_screen, text='CC Basis', font=title_font)
        self.cc_list_frame = ScrollableFrame(self.left_screen)

        self.target_p_ions: list[str] = []
        self.cc_list = CcBasisList(
            self.cc_list_frame.inner_frame,
            self.target_p_ions,
            cast(list[str], self.notebook.lucia_data['states']),
            self.sym.irrep[1:],
        )

        # Save CLSCPLNG.INP
        self.save_button.grid(row=5, column=0, pady=self.SAVE_BUTTON_PADY)

        # Run's all remaining TISE
        self.run_button.config(text='Run TDM conversion')
        self.run_button.grid(row=6, column=0)

    def right_screen_def(self) -> None:
        """Populate widgets displayed on the right-hand pane."""
        ttk.Button(self.right_screen, text='Get Target States', command=self.show_lucia_output).pack(padx=5, pady=5)

        # list of orbital energies
        columns = ['Index', 'State', 'Energy [au]', 'Energy Shift [au]', 'Relative Energy [au]']
        widths = [50, 60, 150, 100, 200]

        cl_frame = ttk.Frame(self.right_screen)
        cl_frame.pack(padx=5, pady=5)

        self.ions_cl = CheckList(
            cl_frame,
            columns=columns,
            p_ions=self.target_p_ions,
            cc_list=self.cc_list,
            units=['au', 'au', 'au'],
        )

        for col, w in zip(columns, widths):
            self.ions_cl.heading(col, text=col)
            self.ions_cl.column(col, width=w)

        self.ions_cl.pack(side=tk.LEFT)

    def show_lucia_output(self) -> None:
        """Grab any new ions calculated by lucia, and add those to the ion_cl and cc_list."""
        if not self.notebook.lucia_data['states']:
            return

        states = cast(list[str], self.notebook.lucia_data['states'])
        energies = cast(list[str], self.notebook.lucia_data['energies'])
        relative_energies = cast(list[str], self.notebook.lucia_data['relative_energies'])

        prev_selected_ions = self.ions_cl.get_checked()
        mults, syms, ions_list, data = self.cc_list.get_data()  # Information from the ccList

        self.ions_cl.erase()

        for ind, (state, energy, relative_energy) in enumerate(
            zip(states, energies, relative_energies),
            1,
        ):
            self.ions_cl.add_item((ind, state, energy, '', relative_energy), state)

        selected_ions = []
        for iid in prev_selected_ions:
            if iid in states:
                selected_ions.append(iid)
                self.ions_cl.toggle(iid)

        # data and new_data are the True/False for the cc_list
        new_data = [[True] * 4] * len(selected_ions) * len(mults)
        for n, ion in enumerate(selected_ions):
            if ion not in ions_list:
                continue

            index = ions_list.index(ion)
            for i in range(len(mults)):
                new_data[i * len(selected_ions) + n] = data[i * len(ions_list) + index]

        self.cc_list.set_lucia_states(states)
        self.cc_list.put(mults, syms, selected_ions, new_data, self.sym.irrep[1:])

    def print_irrep(self, new_sym: bool = False) -> None:
        """Refresh the irreps displayed when the symmetry changes."""
        if not new_sym:
            return

        self.cc_list.add_irrep(self.sym.irrep)

    def erase(self) -> None:
        """Reset widgets and cached data to their default state."""
        self.ions_cl.erase()
        self.cc_list.erase()
        self.cc_list.create()

        self.full_basis_var.set(True)
        self.show_cc_list()
        self.lmax_entry.delete(0, tk.END)
        self.charge_entry.delete(0, tk.END)

    def show_cc_list(self, _event: tk.Event | None = None) -> None:
        """Toggle visibility of the CC basis section."""
        if not self.full_basis_var.get():
            self.cc_basis_label.grid(row=3, column=0, padx=5, pady=5)
            self.cc_list_frame.grid(row=4, column=0, columnspan=10)
        else:
            self.cc_basis_label.grid_forget()
            self.cc_list_frame.grid_forget()

    def run(self) -> None:
        """Run Astra scripts after validating mandatory prerequisites."""
        if not self.notebook.lucia_data['states']:
            missing_required_calculation_popup('Lucia')
            return

        self.run_astra_setup(
            'T',
            'The transformation of the LUCIA results into the ASTRA format',
        )

    def save(self) -> None:
        """Persist the close-coupling configuration to disk."""

        @dataclass
        class ClscplngRequiredFields(RequiredFields):
            lmax: int = 0
            charge: int = 0

            lmax_widget: ttk.Entry = self.lmax_entry
            charge_widget: ttk.Entry = self.charge_entry

        required_fields = ClscplngRequiredFields()

        if not required_fields.check_fields():
            return

        ion_list = self.ions_cl.get_target_states()[:, 0]
        energy_shifts = self.ions_cl.get_energy_shifts_from_checked()
        if ion_list.size == 0:
            required_field_popup('Target states')
            return

        self.notebook.cc_data['lmax'] = required_fields.lmax

        commands = {
            'full_basis': str(self.full_basis_var.get()).upper(),
            'group': self.sym.group.upper(),
            'lmax': required_fields.lmax,
            'charge': required_fields.charge,
            'electrons': self.notebook.lucia_data['electrons'],
            'ion_list': ' '.join(ion_list),
            'occupied': self.notebook.dalton_data['doubly_occupied'],
        }

        str_energy_shifts = [energy_shift or '0.0' for energy_shift in energy_shifts]
        if not all(float(str_energy_shift) == 0 for str_energy_shift in str_energy_shifts):
            commands['energy_shifts'] = 'PARENT_ION_SHIFTS = ' + ' '.join(str_energy_shifts)

        if not self.full_basis_var.get():
            commands['cc_list'] = self.cc_list.save()

        self.save_file(self.CLSCPLNG_FILE, commands, convert_cs_irreps=True)

        bsplines_page = cast('Bsplines', self.notebook.pages[4])
        if self.path_exists(bsplines_page.BSPLINES_INPUT_FILE):
            bsplines_page.save(show_popup=False)

        self.get_cc_data()
        save_success_popup(f'{self.label} inputs saved successfully.')

    def load(self) -> None:
        """Populate the form based on an existing CLSCPLNG.INP file."""

        def get_value_after_equal(lines: list[str], string: str) -> str:
            value = self.get_value_from_lines(lines, string.upper(), shift=0)
            if value:
                return value.split('=')[-1].strip()
            return ''

        def get_mult_and_sym(string: str) -> list[str]:
            """Get the multiplicity and symmetry from the basis list.

            Returns
            -------
            list[str]
                Two-element list containing multiplicity and symmetry.
            """
            # Remove spaces around special characters like [ ] and {
            cleaned_string = re.sub(r'\s*([\[\]\{\}])\s*', r'\1', string)

            # Extract numbers and the rest of the string starting with a letter
            match = re.match(r'\[(\d+)([A-Za-z].*)\]{', cleaned_string)
            if match:
                return list(match.groups())
            return []

        if not self.path_exists(self.CLSCPLNG_FILE):
            return

        lines = self.read_file(self.CLSCPLNG_FILE, convert_cs_irreps=True)

        get_value = partial(get_value_after_equal, lines)

        full_basis_bool = True
        if full_basis_val := get_value('use_full_basis'):
            full_basis_bool = full_basis_val == 'TRUE'
            self.full_basis_var.set(full_basis_bool)
            self.show_cc_list()

        if lmax_val := get_value('lmax'):
            self.lmax_entry.insert(0, lmax_val)
            self.notebook.cc_data['lmax'] = int(lmax_val)

        if charge := get_value('parent_ion_charge'):
            self.charge_entry.insert(0, charge)

        if p_ions_string := get_value('parent_ion_list'):
            self.target_p_ions = p_ions_string.split()

            lucia_ions = cast(list[str], self.notebook.lucia_data['states'])
            for p_ion in self.target_p_ions:
                if p_ion not in lucia_ions or p_ion not in self.ions_cl.get_children():
                    self.cc_list.add_lucia_states([p_ion])
                    self.ions_cl.add_item((0, p_ion, '', '', ''), p_ion)

                self.ions_cl.toggle(p_ion)
        else:
            logger.error('PARENT_ION_LIST is a required argumet for the CLSCPLNG file.')
            return

        if energy_shifts := get_value('parent_ion_shifts'):
            self.set_energy_shifts(self.target_p_ions, energy_shifts.split())

        self.get_cc_data()

        # Exits if using the full basis
        if full_basis_bool:
            return

        mults: list[str] = []
        syms: list[str] = []
        data: list[list[bool]] = []

        while (total_sym_line_ind := self.find_line_ind(lines, '[')) is not None:
            lines = lines[total_sym_line_ind:]
            mult, sym = get_mult_and_sym(lines[0])
            mults.append(mult)
            syms.append(sym)

            for p_ion in self.target_p_ions:
                if p_ion_line_ind := self.find_line_ind(lines, p_ion):
                    temp_data = [label in lines[p_ion_line_ind] for label in CcBasisList.LABELS]
                else:
                    temp_data = [False] * len(CcBasisList.LABELS)

                data.append(temp_data)

            lines = lines[1:]  # "Resets" the lines so that "find_line_ind" doesn't get stuck in the same line

        self.cc_list.put(mults, syms, self.target_p_ions, data, self.sym.irrep[1:])

        self.get_cc_data()
        self.cc_list.check_all_mults()

    def set_energy_shifts(self, parent_ions: list[str], energy_shifts: list[str]) -> None:
        """Update the energy-shift column for the selected ions."""
        for ion, energy_shift in zip(parent_ions, energy_shifts):
            if float(energy_shift) == 0:
                continue

            values = list(self.ions_cl.item(ion, 'values'))
            values[3] = str(energy_shift)
            self.ions_cl.item(ion, values=values)

    @staticmethod
    def get_mult_from_states(states: list[str]) -> list[str]:
        """Extract multiplicities from state strings such as '2A1'.

        Returns
        -------
        list[str]
            Multiplicities (as strings) parsed from the state labels.
        """
        mults: list[str] = []
        for state in states:
            if not (match := re.match(r'(\d+)([A-Za-z].*)', state)):
                continue
            mult, _ = match.groups()
            mults.append(mult)

        return mults

    def get_cc_data(self) -> None:
        """Cache the current CC configuration and show it in the TI notebook."""
        target_states = self.ions_cl.get_target_states()

        if self.full_basis_var.get():
            temp_mults = self.get_mult_from_states(
                cast(list[str], target_states[:, 0].tolist()),
            )
            mults: list[str] = []
            for mult in temp_mults:
                int_mult = int(mult)
                for m in (int_mult - 1, int_mult + 1):
                    if m > 0 and str(m) not in mults:
                        mults.append(str(m))

            temp_syms: list[str] = ['ALL'] * len(mults)

            open_channels = [True] * target_states.shape[0]
        else:
            mults, temp_syms, _, cc_data = self.cc_list.get_data()
            open_channels = cast(list[bool], cc_data[: len(self.target_p_ions), -1].tolist())

        cc_total_syms = []
        for mult, sym in zip(mults, temp_syms):
            if sym == 'ALL':
                cc_total_syms.extend([f'{mult}{irrep}' for irrep in self.sym.irrep[1:]])
            else:
                cc_total_syms.append(f'{mult}{sym}')

        ti_notebook = cast('TimeIndependentNotebook', self.controller.notebooks[2])
        ti_notebook.erase_cc_data()

        ti_notebook.show_cc_data(cc_total_syms, target_states, open_channels)

    def get_outputs(self) -> None:
        """Refresh downstream outputs when CC data changes."""


class CcBasisList:
    """Helper widget that renders and persists close-coupling basis tables."""

    LABELS = ['aiM', 'viM', 'hiG', 'beS']

    def __init__(
        self,
        tab: ttk.Frame,
        p_ions: list[str],
        lucia_states: list[str],
        irrep: list[str],
    ) -> None:
        self.tab = tab
        self.p_ions = p_ions
        self.lucia_states = lucia_states
        self.num_cols = len(self.LABELS)
        self.irrep = irrep

        self.length = 0
        self.create()

    def create(self, length: int = 1) -> None:
        """Initialise table widgets for the configured number of rows."""
        self.mults: list[ttk.Entry] = []
        self.syms: list[ttk.Combobox] = []
        self.hidden_widgets: dict[int, list[tk.Widget]] = {}
        self.hidden_widgets_data: dict[int, list[bool]] = {}
        self.columns: list[list[ttk.Checkbutton]] = [[] for _ in range(self.num_cols)]
        self.remove_buttons: list[ttk.Button] = []
        self.add_button = ttk.Button(self.tab, width=1, text='+', command=self.add_sym)

        for _ in range(length):
            self.add_sym()

    def p_ion_col_ind(self, ind: int, p_ion_ind: int) -> int:
        """Return the column index for a given symmetry row and ion.

        Returns
        -------
        int
            Column index associated with the ion at the specified row.
        """
        return p_ion_ind + ind * len(self.p_ions)

    def p_ion_grid_ind(self, ind: int, p_ion_ind: int) -> int:
        """Return the grid index for a given symmetry row and ion.

        Returns
        -------
        int
            Grid row index for the ion widgets.
        """
        return self.p_ion_col_ind(ind, p_ion_ind) + 4 * ind + 3

    def start_row(self, ind: int) -> int:
        """Return the first grid row used by the specified symmetry block.

        Returns
        -------
        int
            Base grid row index for the block.
        """
        return (len(self.p_ions) + 4) * ind  # 4 is the number of widgets that are always shown for each added symmetry

    def add_p_ion(self, p_ion: str) -> None:
        """Add UI widgets for a new parent ion."""
        p_ion_ind = self.sorted_p_ions().index(p_ion)

        # If ion is not currently hidden, make space for it
        if not self.hidden_widgets_data.get(p_ion_ind):
            self.make_space_for_ion(p_ion_ind)

        for ind in range(self.length):
            col_ind = self.p_ion_col_ind(ind, p_ion_ind)
            grid_ind = self.p_ion_grid_ind(ind, p_ion_ind)

            if self.hidden_widgets.get(grid_ind):
                self.show_row(col_ind, grid_ind)
            else:
                ttk.Button(
                    self.tab,
                    text=p_ion,
                    command=partial(self.toggle_row, ind * len(self.p_ions) + p_ion_ind),
                ).grid(row=grid_ind, column=2)
                for col in range(self.num_cols):
                    w = ttk.Checkbutton(self.tab, variable=tk.BooleanVar(value=True))
                    self.columns[col].insert(col_ind, w)
                    w.grid(row=grid_ind, column=col + 3)

    def make_space_for_ion(self, p_ion_ind: int) -> None:
        """Move widgets down to make space for new ion."""
        start_ind = self.p_ion_grid_ind(0, p_ion_ind)
        last_row = self.length * (len(self.p_ions) + 4) + 1

        count = 1
        for row in range(last_row, start_ind - 1, -1):
            if row == self.p_ion_grid_ind(count + 1, p_ion_ind):
                count += 1

            for col in range(8):
                for widget in self.tab.grid_slaves(row=row, column=col):
                    widget.grid(row=row + count, column=col)

    def remove_p_ion(self, p_ion: str) -> None:
        """Remove widgets associated with a parent ion."""
        p_ion_ind = self.sorted_p_ions().index(p_ion)
        for ind in range(self.length):
            col_ind = self.p_ion_col_ind(ind, p_ion_ind)
            grid_ind = self.p_ion_grid_ind(ind, p_ion_ind)
            self.hide_row(col_ind, grid_ind)

    def set_lucia_states(self, lucia_states: list[str]) -> None:
        """Reset the lucia states for the object."""
        self.lucia_states = lucia_states

    def add_lucia_states(self, lucia_states: list[str]) -> None:
        """Reset the lucia states for the object."""
        self.lucia_states.extend(lucia_states)

    def add_irrep(self, irrep: list[str]) -> None:
        """Update the list of irreps available to the selection widgets."""
        self.irrep = irrep
        for sym in self.syms:
            sym.configure(values=self.irrep)
            sym.set('')

    def total_syms(self) -> list[str]:
        """Return a list of the total symmetries added to the cc basis list.

        Returns
        -------
        list[str]
            Concatenated multiplicity and symmetry strings.
        """
        return [mult.get().strip() + sym.get() for mult, sym in zip(self.mults, self.syms)]

    def add_sym(self) -> None:
        """Add a single line from the table and prints the new version on the screen."""
        for i in range(self.num_cols):
            for _ in range(len(self.p_ions)):
                w = ttk.Checkbutton(self.tab, variable=tk.BooleanVar(value=True))
                self.columns[i].append(w)

        self.mults.append(ttk.Entry(self.tab, width=3))
        self.syms.append(ttk.Combobox(self.tab, width=3, values=self.irrep))
        self.remove_buttons.append(
            ttk.Button(self.tab, text='-', width=1, command=partial(self.remove_sym, self.length)),
        )

        self.length += 1

        self.grid(self.length - 1)

    def remove_sym(self, ind: int) -> None:
        """Remove a symmetry row and tidy up associated widgets."""
        self.mults.pop(ind).destroy()
        self.syms.pop(ind).destroy()

        for _ in self.p_ions:
            for j in range(self.num_cols):
                self.columns[j].pop(ind * len(self.p_ions)).destroy()

        self.remove_buttons.pop().destroy()
        self.length -= 1
        for i in range(ind, self.length):
            self.remove_labels(i)
            self.grid(i)
        self.remove_labels(self.length)

    def remove_labels(self, ind_: int | None = None) -> None:
        """
        Remove all labels.

        These are widgets that do not get removed by other methods by default.
        """
        inds = list(range(self.length)) if ind_ is None else [ind_]

        for ind in inds:
            start_row = self.start_row(ind)
            for j in [0, 2]:  # Mult/Sym and self.LABELS
                for col in range(7):
                    for widget in self.tab.grid_slaves(row=start_row + j, column=col):
                        widget.destroy()

            # p_ion labels
            for p_ion_ind in range(len(self.p_ions)):
                for widget in self.tab.grid_slaves(row=start_row + 3 + p_ion_ind, column=2):
                    widget.destroy()

    def toggle_column(self, ind: int) -> None:
        """If all cells in column have the same value, turn them toggle them, if not, turn them to False."""
        all_same = True
        val = self.columns[ind][0].instate(['selected'])
        if any(cell.instate(['selected']) != val for cell in self.columns[ind][1:]):
            all_same = False

        for cell in self.columns[ind]:
            if all_same:
                cell.invoke()
            else:
                val = cell.instate(['selected'])
                if not val:  # Only flips the ones that are not selected
                    cell.invoke()

    def toggle_row(self, ind: int) -> None:
        """If all cells in row have the same value, turn them toggle them, if not, turn them to False."""
        all_same = True
        val = self.columns[0][ind].instate(['selected'])
        for i in range(1, self.num_cols):
            cur_val = self.columns[i][ind].instate(['selected'])
            if val != cur_val:
                all_same = False

        for i in range(self.num_cols):
            cell = self.columns[i][ind]
            if all_same:
                cell.invoke()
            else:
                val = cell.instate(['selected'])
                if not val:  # Only flips the ones that are true
                    cell.invoke()

    def hide_row(self, col_ind: int, grid_ind: int) -> None:
        """Temporarily hide a row while remembering its previous state."""
        hidden_widgets: list[tk.Widget] = []
        hidden_widgets_data: list[bool] = []
        for i in range(self.num_cols):
            cell = self.columns[i][col_ind]
            val = cell.instate(['selected'])
            hidden_widgets_data.append(val)
            # Turns all cells in that row to False
            if val:
                cell.invoke()

        for col in range(2, 7):
            for widget in self.tab.grid_slaves(row=grid_ind, column=col):
                hidden_widgets.append(widget)
                widget.grid_remove()

        # This is needed in case the user types fast and the code is executed multiple times unintentionally
        if hidden_widgets == []:
            return

        self.hidden_widgets[grid_ind] = hidden_widgets
        self.hidden_widgets_data[col_ind] = hidden_widgets_data

    def show_row(self, col_ind: int, grid_ind: int) -> None:
        """Restore a previously hidden row."""
        for widget in self.hidden_widgets.pop(grid_ind, []):
            widget.grid()

        # Restores the data previously stored in that row
        col_vals = self.hidden_widgets_data.pop(col_ind, [])
        for col, val in zip(range(self.num_cols), col_vals):
            cell = self.columns[col][col_ind]
            if val:
                cell.invoke()

    def check_mult(self, _event: tk.Event | None = None, ind: int = 0) -> None:
        """Check multiplicity in the combobox and hides the proper rows."""
        try:
            mult = int(self.mults[ind].get().strip())
        except ValueError:
            return  # Skips if mult is not a number

        for p_ion_ind, p_ion in enumerate(self.p_ions):
            if not (match := re.match(r'(\d+)([A-Za-z].*)', p_ion)):
                continue

            ion_mult, _ = match.groups()

            col_ind = ind * len(self.p_ions) + p_ion_ind
            grid_ind = (len(self.p_ions) + 4) * ind + p_ion_ind + 3
            if np.abs(mult - int(ion_mult)) != 1:
                self.hide_row(col_ind, grid_ind)
            else:
                self.show_row(col_ind, grid_ind)

    def check_all_mults(self) -> None:
        """Check all multiplicities in the comboboxes and hides the proper rows."""
        for ind in range(self.length):
            self.check_mult(ind=ind)

    def sorted_p_ions(self) -> list[str]:
        """Return a list of target ions sorted by energy.

        Returns
        -------
        list[str]
            Parent ions sorted by their energy ordering.
        """
        return sorted(self.p_ions, key=self.lucia_states.index)

    def grid(self, ind_: int | None = None) -> None:
        """Print the a specific symmetry index or the whole table to the screen."""
        inds = [ind_] if ind_ is not None else list(range(self.length))

        for ind in inds:
            start_row = self.start_row(ind)
            ttk.Label(self.tab, text='Mult').grid(row=start_row, column=0)
            ttk.Label(self.tab, text='Sym').grid(row=start_row, column=1)

            self.mults[ind].bind('<KeyRelease>', partial(self.check_mult, ind=ind))

            self.mults[ind].grid(row=start_row + 1, column=0)
            self.syms[ind].grid(row=start_row + 1, column=1)

            for label_ind, label in enumerate(self.LABELS):
                ttk.Button(self.tab, text=label, command=partial(self.toggle_column, label_ind)).grid(
                    row=start_row + 2,
                    column=label_ind + 3,
                )

            for p_ion_ind, p_ion in enumerate(self.sorted_p_ions()):
                ttk.Button(
                    self.tab,
                    text=p_ion,
                    command=partial(self.toggle_row, ind * len(self.p_ions) + p_ion_ind),
                ).grid(row=start_row + 3 + p_ion_ind, column=2)
                for j in range(self.num_cols):
                    self.columns[j][ind * len(self.p_ions) + p_ion_ind].grid(
                        row=start_row + p_ion_ind + 3,
                        column=j + 3,
                    )

            self.remove_buttons[ind].grid(row=start_row + len(self.p_ions) + 3, column=self.num_cols + 3)

        self.add_button.grid(row=(len(self.p_ions) + 4) * self.length + 1, column=self.num_cols + 3, pady=5)

        self.check_all_mults()

    def save(self) -> str:
        """Serialise the CC basis table into the CLSCPLNG input format.

        Returns
        -------
        str
            Saved representation of the CC basis list.
        """
        lines = []
        for i in range(self.length):
            syms = [self.syms[i].get().strip()]

            if syms[0] == 'ALL':
                syms = self.irrep[1:]

            for sym in syms:
                total_symmetry = self.mults[i].get().strip() + sym
                lines.append(f'\n[{total_symmetry}]{{')
                for j, p in enumerate(self.sorted_p_ions()):
                    # Checks if at least one orbital is selected for specific ion (especially important for hidden ions)
                    flag = False
                    s = f'\t{p} ( '
                    ind = j + i * len(self.p_ions)
                    for label_ind, label in enumerate(self.LABELS):
                        if self.columns[label_ind][ind].instate(['selected']):
                            flag = True
                            if label_ind == self.LABELS.index('beS'):
                                s += f'{label}:ALL_XLM '
                            else:
                                s += f'{label} '
                    s += ')'
                    if flag:
                        lines.append(s)
                lines.append('}')

        return '\n'.join(lines).replace("'", 'p')

    def put(
        self,
        mults: list[str],
        syms: list[str],
        p_ions: list[str],
        ions_data: list[list[bool]],
        irrep: list[str],
    ) -> None:
        """Load table data previously produced by `save`."""

        @dataclass
        class State:
            # Makes checking for "all" symmetry easier
            mult: str
            syms: list[str]
            data: list[list[bool]]

        self.erase()

        # This needs to be done so that self.p_ions is still has the same id as ions_cl.p_ions
        self.p_ions.extend(p_ions)

        if len(mults) == 0:
            self.create()
            return

        num_p_ions = len(p_ions)

        # Checks if "all" symmetry was used
        temp_data = [State(mults[0], syms[:1], ions_data[:num_p_ions])]
        for ind in range(1, len(mults)):
            mult = mults[ind]
            sym = syms[ind]
            ion_data = ions_data[num_p_ions * ind : num_p_ions * (ind + 1)]

            flag = False
            for t_data in temp_data:
                if t_data.mult == mult and sym not in t_data.syms and t_data.data == ion_data:
                    t_data.syms.append(sym)
                    flag = True

            if not flag:
                temp_data.append(State(mult, [sym], ion_data))

        # Converts CC basis data to easier format to load
        mults = []
        syms = []
        ions_data = []
        for t_data in temp_data:
            if len(t_data.syms) == len(irrep):
                t_data.syms = ['ALL']

            for sym in t_data.syms:
                mults.append(t_data.mult)
                syms.append(sym)
                for data in t_data.data:
                    ions_data.append(data)

        # loads data into table
        self.create(len(mults))

        for ind, mult in enumerate(mults):
            self.mults[ind].insert(0, mult)

        for ind, sym in enumerate(syms):
            self.syms[ind].set(sym)

        for row, data in enumerate(ions_data):
            for col, cell in enumerate(data):
                # The default value of all checkbuttons is True,
                # so if the cell is false, we have to flip the checkbutton
                if not cell:
                    self.columns[col][row].invoke()

    def get_data(self) -> tuple[list[str], list[str], list[str], np.ndarray]:
        """Return the current multiplicities, symmetries, ions, and selection matrix.

        Returns
        -------
        tuple[list[str], list[str], list[str], np.ndarray]
            Multiplicities, symmetries, parent ions, and selection mask.
        """
        mults: list[str] = [m.get().strip() for m in self.mults]
        syms: list[str] = [s.get().strip() for s in self.syms]
        data: list[list[bool]] = []

        for col in self.columns:
            row = [cell.instate(['selected']) for cell in col]
            data.append(row)

        return mults, syms, self.p_ions, np.array(data).T

    def erase(self) -> None:
        """Remove all dynamically created widgets and reset internal structures."""
        for i in reversed(range(self.length)):
            self.remove_sym(i)

        for row in list(self.hidden_widgets):
            for widget in self.hidden_widgets.pop(row):
                widget.destroy()

        self.add_button.destroy()
        self.p_ions.clear()


class CheckList(ttk.Treeview):
    """Treeview that behaves like a checklist with unit conversion helpers."""

    ENERGY_SHIFT_COL = '#4'

    def __init__(self, frame: ttk.Frame, p_ions: list[str], cc_list: CcBasisList, units: list[str], **kwargs) -> None:
        ttk.Treeview.__init__(self, frame, **kwargs, height=20)
        self.unchecked = '[  ]'
        self.checked = '[X]'
        self.p_ions = p_ions
        self.cc_list = cc_list

        self.column('#0', width=50)
        self.heading('#0', text='', command=self.toggle_all)
        self.bind('<Button-1>', self.item_click, add=True)
        self.bind('<Double-1>', self.double_click, add=True)

        for ind, unit in enumerate(units, 2):
            col = self['columns'][ind]
            self.heading(col, command=partial(self.change_units, ind, unit))

    def item_click(self, event: tk.Event) -> None:
        """Toggle a checkbox when the row text is clicked."""
        x, y = event.x, event.y
        element = self.identify('element', x, y)
        if element == 'text':
            iid = self.identify_row(y)
            self.toggle(iid)

    def double_click(self, event: tk.Event) -> None:
        """Edit the energy shift value for the clicked row."""
        iid = self.identify_row(event.y)
        col = self.identify_column(event.x)
        if not iid or col != self.ENERGY_SHIFT_COL:  # Only works for the energy shift column
            return

        x, y, width, height = self.bbox(iid, col)
        value = self.set(iid, col)

        entry = tk.Entry(self)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def on_return(_event: tk.Event) -> None:
            shift = entry.get().strip()
            if shift:
                try:
                    shift = float(shift)
                except ValueError:
                    invalid_input_popup('Please enter a valid number for the energy shift.')
                    shift = None

            if shift is not None:
                self.set(iid, col, str(shift))
                self.update_relative_energies()

            entry.destroy()

        entry.bind('<Return>', on_return)
        entry.bind('<FocusOut>', lambda _e: entry.destroy())

    def update_relative_energies(self) -> None:
        """Recompute the relative energy column based on current shifts."""
        first_energy = 0
        for ind, iid in enumerate(self.get_children()):
            values = list(self.item(iid, 'values'))

            shift = float(values[3]) if values[3] else 0
            cur_energy = float(values[2]) + shift

            relative = cur_energy - first_energy
            if ind == 0:
                first_energy = cur_energy
                relative = 0

            values[4] = str(relative)
            self.item(iid, values=values)

    def add_item(self, item: tuple[int, str, str, str, str], label: str) -> None:
        """Add an item to the checklist."""
        self.insert('', index='end', iid=label, text=self.unchecked, values=item, open=True)

    def change_units(self, ind: int, units: str) -> None:
        """Toggle between atomic units and eV for the specified column."""
        for item in self.get_children():
            values = list(self.item(item, 'values'))

            if not (value := values[ind]):
                continue

            value = float(value)
            value *= EV_TO_AU if units == 'eV' else AU_TO_EV

            values[ind] = str(value)

            self.item(item, values=values)

        new_units = 'eV' if units == 'au' else 'au'

        col = self['columns'][ind]
        heading_text = self.heading(col)['text'].replace(units, new_units)
        self.heading(col, text=heading_text, command=partial(self.change_units, ind, new_units))

    def get_checked(self) -> list[str]:
        """Return a list of the target states that were selected.

        Returns
        -------
        list[str]
            Identifiers for every checked row.
        """
        return [iid for iid in self.get_children() if self._checked(iid)]

    def toggle_all(self) -> None:
        """Toggle every row, flipping between all-selected and none-selected."""
        all_rows_same = True
        all_checked = self.get_checked()
        iids = self.get_children()

        # Checks if all rows are checked or not checked
        if len(all_checked) not in {0, len(iids)}:
            all_rows_same = False

        for iid in iids:
            if all_rows_same or not self._checked(iid):
                self.toggle(iid)

    def toggle(self, iid: str) -> None:
        """Toggle checkbox."""
        if self._checked(iid):
            self.uncheck(iid)
            self.cc_list.remove_p_ion(iid)
            self.p_ions.remove(iid)
        else:
            self.check(iid)
            self.p_ions.append(iid)
            self.cc_list.add_p_ion(iid)

    def get_energy_shifts_from_checked(self) -> list[str]:
        """Return the energy-shift column for every selected ion.

        Returns
        -------
        list[str]
            Energy shift values corresponding to checked ions.
        """
        shift_energies = []
        for iid in self.get_checked():
            values = self.item(iid, 'values')
            shift = values[3]

            if shift and 'eV' in self.heading(self.ENERGY_SHIFT_COL)['text']:
                shift = str(float(shift) * EV_TO_AU)

            shift_energies.append(shift)

        return shift_energies

    def get_target_states(self, shift_energies: bool = True) -> np.ndarray:
        """Return a matrix with the selected states and their energies.

        Returns
        -------
        np.ndarray
            Two-dimensional array containing states, energies, and relative energies.
        """
        states: list[str] = []
        energies: list[str] = []
        relative_energies: list[str] = []
        for iid in self.get_checked():
            _, state, energy, energy_shifts, relative_energy = self.item(iid, 'values')
            states.append(state)

            if shift_energies and energy:
                energy_shifts = float(energy_shifts) if energy_shifts else 0
                energy = str(float(energy) + energy_shifts)

            energies.append(energy)
            relative_energies.append(relative_energy)

        return np.column_stack((states, energies, relative_energies))

    def _checked(self, iid: str) -> bool:
        """Return True if checkbox ``iid`` is checked.

        Returns
        -------
        bool
            True when the item is marked as checked.
        """
        text = self.item(iid, 'text')
        return text == self.checked

    def check(self, iid: str) -> None:
        """Check the checkbox 'iid'."""
        if not self._checked(iid):
            self.item(iid, text=self.checked)

    def uncheck(self, iid: str) -> None:
        """Uncheck the checkbox 'iid'."""
        if self._checked(iid):
            self.item(iid, text=self.unchecked)

    def erase(self) -> None:
        """Clear the checklist and synchronised ion state list."""
        self.p_ions.clear()
        for item in self.get_children():
            self.delete(item)
