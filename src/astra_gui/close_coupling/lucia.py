"""Notebook page that configures Lucia calculations and parses outputs."""

import logging
import re
import tkinter as tk
from collections import defaultdict
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, cast

import numpy as np
from moldenViz import Plotter

from astra_gui.utils.font_module import title_font
from astra_gui.utils.logger_module import log_operation
from astra_gui.utils.popup_module import (
    missing_output_popup,
    missing_required_calculation_popup,
    required_field_popup,
    warning_popup,
)
from astra_gui.utils.required_fields_module import RequiredFields
from astra_gui.utils.scrollable_module import ScrollableTreeview
from astra_gui.utils.table_module import Table

from .cc_notebook_page_module import CcNotebookPage
from .dalton import Dalton

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .clscplng import Clscplng
    from .create_cc_notebook import CreateCcNotebook


class Lucia(CcNotebookPage):
    """Notebook page responsible for running Lucia and managing its inputs."""

    LUCIA_FILE = Path('LUCIA.INP')
    LUCIA_SA_FILE = Path('LUCIA_SA.INP')
    SCRIPT_COMMANDS = ['lucia.x']

    OUTPUT_FILES = {
        'Target states': Path('QC/Lucia_Loc_H.out'),
        'Hamiltonian': Path('QC/Lucia_Loc_H.out'),
        'Transition density matrices': Path('QC/Lucia_TDM1-2B.out'),
    }

    def __init__(self, notebook: 'CreateCcNotebook') -> None:
        super().__init__(notebook, 'Molecular States', two_screens=True)

        self.middle_screen_def()

        self.plotter = None

    def left_screen_def(self) -> None:
        """Build the widgets shown on the left-hand panel."""
        self.inact_act_orb_frame = ttk.Frame(self.left_screen)
        self.inact_act_orb_frame.grid(row=0, column=0, columnspan=10)

        ttk.Label(self.inact_act_orb_frame, text='Inactive orbitals:').grid(row=1, column=0)
        ttk.Label(self.inact_act_orb_frame, text='Active orbitals:').grid(row=2, column=0)

        # Entry widgets are created in the "print_irrep" function

        # Number of electrons
        self.hover_widget(
            ttk.Label,
            self.left_screen,
            text="Target's number of electrons:",
            hover_text='Total number of electrons',
        ).grid(row=1, column=0)
        self.electrons_entry = ttk.Entry(self.left_screen, width=10)
        self.electrons_entry.grid(row=1, column=1)

        # White space
        self.left_screen.grid_rowconfigure(2, minsize=30)

        # Target states
        ttk.Label(self.left_screen, text='Target States:', font=title_font).grid(row=3, column=0, columnspan=2)
        states_frame = ttk.Frame(self.left_screen)
        states_frame.grid(row=4, column=0, columnspan=10)
        self.states_table = Table(
            states_frame,
            ['Symmetry', 'Multiplicity', 'Number of States'],
            width=8,
            col_types=['combobox', 'entry', 'entry'],
            combobox_values_list=[[]],
        )

        self.left_screen.grid_rowconfigure(5, minsize=10)

        ttk.Label(self.left_screen, text='State average calculation:').grid(row=6, column=0)
        self.sa_var = tk.BooleanVar(value=False)
        show_sa_button = ttk.Checkbutton(self.left_screen, variable=self.sa_var, command=self.show_sa)
        show_sa_button.grid(row=6, column=1, sticky='w')

        self.save_button.grid(row=7, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=8, column=0)

    def middle_screen_def(self) -> None:
        """Initialise the middle panel that controls state-averaged inputs."""
        self.middle_screen = ttk.Frame(self)
        ttk.Label(self.middle_screen, text='State Average', font=title_font).pack()
        sa_frame = ttk.Frame(self.middle_screen)
        sa_frame.pack()

        self.sa_inact_act_orb_frame = ttk.Frame(sa_frame)
        self.sa_inact_act_orb_frame.grid(row=0, column=0, columnspan=10, pady=10, sticky='w')

        ttk.Label(self.sa_inact_act_orb_frame, text='Inactive orbitals:').grid(row=1, column=0)
        ttk.Label(self.sa_inact_act_orb_frame, text='Active orbitals:').grid(row=2, column=0)

        # Entry widgets are created in the "print_irrep" function

        self.hover_widget(
            ttk.Label,
            sa_frame,
            text="Target's number of electrons:",
            hover_text='Total number of electrons',
        ).grid(row=1, column=0)
        self.sa_electrons_entry = ttk.Entry(sa_frame, width=10)
        self.sa_electrons_entry.grid(row=1, column=1)

        # Averaged states
        ttk.Label(sa_frame, text='Averaged States:', font=title_font).grid(row=2, column=0, pady=10)
        sa_states_frame = ttk.Frame(sa_frame)
        sa_states_frame.grid(row=3, column=0, columnspan=10)
        self.sa_states_table = Table(
            sa_states_frame,
            ['Weight', 'Symmetry', 'Multiplicity', 'Number of States'],
            width=8,
            col_types=['entry', 'combobox', 'entry', 'entry'],
            combobox_values_list=[[]],
            default_values=['1.0', '', '', ''],
        )

    def right_screen_def(self) -> None:
        """Build widgets for orbital inspection on the right-hand panel."""
        get_orbitals_button = ttk.Button(self.right_screen, text='Get Orbitals', command=self.show_dalton_output)
        get_orbitals_button.pack(padx=5, pady=5)

        self.plot_orbitals_button = ttk.Button(self.right_screen, text='Plot Orbitals', command=self.plot_orbitals)
        self.plot_orbitals_button.pack(padx=5, pady=5)

        # list of orbital energies
        treeview_frame = ttk.Frame(self.right_screen)
        treeview_frame.pack(padx=5, pady=5)

        columns = ['Index', 'Symmetry', 'Energy [au]']
        widths = [50, 70, 120]

        self.orbs_tv = ScrollableTreeview(treeview_frame, columns=columns, show='headings', height=20)
        for col, w in zip(columns, widths):
            self.orbs_tv.heading(col, text=col)
            self.orbs_tv.column(col, width=w)

        self.orbs_tv.pack(side=tk.LEFT)

    def plot_orbitals(self) -> None:
        """Launch the orbitals plotter when the required data is available."""
        if not (self.path_exists(self.MOLDEN_FILE) and self.path_exists(Dalton.OUTPUT_FILE)):
            missing_output_popup('Dalton')
            return

        # Check if the plotter is already open
        if self.plotter and self.plotter.on_screen:
            return

        molden_lines = self.read_file(self.MOLDEN_FILE, empty_lines=True)

        self.plotter = Plotter(molden_lines, tk_root=self.controller)

    def show_dalton_output(self) -> None:
        """Populate the orbitals table with results from the Dalton run."""
        if not self.path_exists(Dalton.OUTPUT_FILE):
            missing_output_popup('Dalton')
            return

        if 'orbital_energies' not in self.notebook.dalton_data:
            logger.warning('Dalton output detected: orbital energies missing from cache')

        if not self.notebook.dalton_data['orbital_energies']:
            return

        # Erases all the previous orbital information
        for item in self.orbs_tv.get_children():
            self.orbs_tv.delete(item)

        orbital_energies = self.convert_orbital_energies()

        occupied_orbs = orbital_energies[orbital_energies[:, 1].astype(float) < 0]
        virtual_orbs = orbital_energies[orbital_energies[:, 1].astype(float) >= 0]
        homo = occupied_orbs[occupied_orbs[:, 1].astype(float).argmax()].tolist()
        lumo = virtual_orbs[virtual_orbs[:, 1].astype(float).argmin()].tolist()
        for ind, orbital in enumerate(orbital_energies, 1):
            self.orbs_tv.insert('', 'end', values=(ind, *orbital))

        self.delete_homo_lumo_labels()
        for label, data in zip(['HOMO', 'LUMO'], [homo, lumo]):
            ttk.Label(self.right_screen, text=f'{label}: {" | ".join(data)} au').pack()

    def convert_orbital_energies(self) -> np.ndarray:
        """Parse and sort the orbital energies returned by Dalton.

        Returns
        -------
        np.ndarray
            Two-column array containing orbital labels and energies.
        """

        def sort_energies(data: np.ndarray) -> np.ndarray:
            sorted_indices = np.argsort(data[:, 1].astype(float))
            return data[sorted_indices]

        orb_energies = cast(str, self.notebook.dalton_data['orbital_energies'])

        parsed_data = []
        cur_sym = None

        count = 0
        for line in orb_energies.strip().split('\n'):
            if re.match(r'^\d\s+', line):
                parts = line.split()
                cur_sym = f'{parts[1]}'
                values = list(map(float, parts[2:]))
                count = 1
            else:
                values = list(map(float, line.split()))

            for v in values:
                parsed_data.append([f'{cur_sym}.{count}', v])
                count += 1

        return sort_energies(np.array(parsed_data))

    def error_function(self) -> tuple[bool, str]:
        """Assess whether Lucia produced valid outputs and attempt recovery.

        Returns
        -------
        tuple[bool, str]
            Success flag and error message describing any issues.
        """

        def successful_calculation(file: Path) -> bool:
            content = self.read_file_content(file)
            return 'STOP  I am home from the loops' in content

        def get_new_dimension_requirement() -> int:
            lines = self.read_file(self.OUTPUT_FILES['Hamiltonian'])
            for line in lines:
                match = re.search(r'^\s*Required dimension is\s+(\d+)$', line)
                if match:
                    return int(match.group(1)) * 2
            return 0

        if self.sa_var.get():
            self.OUTPUT_FILES['State Average'] = Path('QC/Lucia_State-Ave.out')

        if not any(self.path_exists(file) for file in self.OUTPUT_FILES.values()):
            return False, 'No Lucia output was generated.'

        success = True
        errors: list[str] = []
        for label, file in self.OUTPUT_FILES.items():
            if not self.path_exists(file) or not successful_calculation(file):
                errors.append(label)
                success = False

        error_string = ''
        if len(errors) > 0:
            s = f'{", ".join(errors[:-1])}, and {errors[-1]}' if len(errors) > 2 else ' and '.join(errors)  # noqa: PLR2004
            error_string = f'{s} calculation(s) were not successful.'

        if self.path_exists(self.OUTPUT_FILES['Hamiltonian']) and not successful_calculation(
            self.OUTPUT_FILES['Hamiltonian'],
        ):
            if not (lcsblk := get_new_dimension_requirement()):
                return success, error_string

            self.notebook.lucia_data['lcsblk'] = lcsblk

            error_string += '\nUpdating LUCIA.INP and running Hamiltonian calculation again.'

            self.save()

            if self.sa_var.get():
                self.run_astra_setup('-run eht --sa', 'State average')
            else:
                self.run_astra_setup('-run eht', 'Lucia')

        return success, error_string

    def delete_homo_lumo_labels(self) -> None:
        """
        Delete all widgets under treeview_frame.

        This will delete the HOMO/LUMO lines since they are the only widgets under the orbitals table.
        """
        treeview_frame = self.orbs_tv.master
        parent_frame = cast(ttk.Frame, treeview_frame.master)

        found_widget = False
        for child in parent_frame.winfo_children():
            if found_widget:
                child.destroy()
            if child == treeview_frame:
                found_widget = True

    def run(self) -> None:
        """Execute Lucia or state-average calculations after verifying inputs."""
        if not self.path_exists(Dalton.OUTPUT_FILE):
            missing_required_calculation_popup('Dalton')
            return

        if self.sa_var.get():
            self.run_astra_setup('eht --sa', 'State average')
        else:
            self.run_astra_setup('eht', 'Lucia')

    @staticmethod
    def get_states_list(states_data: np.ndarray) -> list[str]:
        """Get list of states calculated by Lucia.

        Returns
        -------
        list[str]
            Expanded list of state identifiers with counters.
        """
        states_list: list[str] = []
        for state in states_data:
            states_list.extend([f'{state[1]}{state[0]}'] * int(state[-1]))

        counter: dict[str, int] = defaultdict(
            int,
        )  # Starts a dictionary where if a key doesn't exist, it's initial value is 0
        states_with_counter: list[str] = []

        # Counts the ions with the same multiplicity/symmetry
        for state in states_list:
            counter[state] += 1
            states_with_counter.append(f'{state}.{counter[state]}')

        return states_with_counter

    def load_states_data(
        self,
        lines: list[str],
        num_states_line_ind: int,
        sa: bool = False,
    ) -> np.ndarray:
        """Read target-state blocks from the Lucia input files.

        Returns
        -------
        np.ndarray
            Structured array describing states and associated metadata.
        """

        @dataclass
        class StateCounter:
            state: np.ndarray
            count: int

        num_computed_states = int(lines[num_states_line_ind])

        states_data_list: list[list[str]] = []
        for i in range(
            num_states_line_ind + 1,
            num_states_line_ind + 1 + num_computed_states,
        ):
            states_data_list.append(lines[i].split())  # noqa: PERF401

        states_data_array = np.array(states_data_list).astype(object)

        if not sa:
            states_data_array[:, 0] = np.array([self.sym.irrep[i] for i in states_data_array[:, 0].astype('int')])
            self.notebook.lucia_data['states'] = self.get_states_list(states_data_array)
        else:
            states_data_array[:, 0] = np.array([float(i.replace('D', 'E')) for i in states_data_array[:, 0]])
            states_data_array[:, 1] = np.array([self.sym.irrep[i] for i in states_data_array[:, 1].astype('int')])
            states_data_array = np.delete(states_data_array, [3, 4], axis=1)

            # Get's the number of "similar" states for SA
            states_counter = [StateCounter(states_data_array[0], 1)]
            for i, state in enumerate(states_data_array[1:], 1):
                if np.any(np.all(state == states_data_array[:i], axis=1)):
                    states_counter[-1].count += 1
                else:
                    states_counter.append(StateCounter(states_data_array[i], 1))

            states_data_array = np.array([state.state for state in states_counter])
            count_array = np.array([state.count for state in states_counter])

            states_data_array = np.insert(states_data_array, 3, count_array, axis=1)

        # Checks if a "all" symmetry was used, by adding the symmetries of "similar" states together
        sym_ind = 1 if sa else 0  # Column index for the symmetry
        states_data_array = self.pack_all_sym(states_data_array, sym_ind).astype(object)

        s = [0, 2, 3] if sa else slice(1, None)

        states_counter = [StateCounter(states_data_array[0], 1)]
        for state in states_data_array[1:]:
            flag = True
            for state_counter in states_counter:
                if np.array_equal(state_counter.state[s], state[s]):
                    state_counter.state[sym_ind] += f',{state[sym_ind]}'
                    state_counter.count += 1
                    flag = False
                    break
            if flag:
                states_counter.append(StateCounter(state, 1))

        # After all states were added together, check if we have enough to make "all" symmetry
        states_data_list = []
        for state in states_counter:
            if state.count == len(self.sym.irrep) - 1:
                state.state[sym_ind] = 'ALL'
                states_data_list.append(cast(list[str], state.state.tolist()))
            else:
                syms = state.state[sym_ind].split(',')
                for sym in syms:
                    state.state[sym_ind] = sym
                    states_data_list.append(cast(list[str], state.state.tolist()))

        states_data_array = np.array(states_data_list)

        indices = list(range(states_data_array.shape[0]))
        if not sa:
            indices.sort(
                key=lambda i: (
                    self.sym.irrep.index(states_data_array[i, 0]),
                    states_data_array[i, 1],
                ),
            )
        else:
            indices.sort(
                key=lambda i: (
                    self.sym.irrep.index(states_data_array[i, 1]),
                    states_data_array[i, 2],
                ),
            )

        return states_data_array[indices, :]

    @log_operation('loading LUCIA')
    def load(self) -> None:
        """Populate the page with values from the LUCIA input files."""
        if not self.path_exists(self.LUCIA_FILE):
            return

        lines = self.read_file(self.LUCIA_FILE, '*')

        find_line_ind = partial(self.find_line_ind, lines)
        get_value = partial(self.get_value_from_lines, lines)

        inact_orbs: list[int] = []
        if inact_str_list := get_value('Inash').split(','):
            inact_orbs = [int(i) for i in inact_str_list]

        act_orbs: list[int] = []
        if atc_str_list := get_value('GASSH', 2).split(','):
            act_orbs = [int(a) for a in atc_str_list]

        self.notebook.lucia_data['total_orbitals'] = [str(i + a) for i, a in zip(inact_orbs, act_orbs)]

        for row, list_orbs in enumerate([inact_orbs, act_orbs], start=1):
            for col, orb in enumerate(list_orbs, 1):
                widget = self.get_widget_from_grid(self.inact_act_orb_frame, row, col)
                assert isinstance(widget, ttk.Entry)
                widget.delete(0, tk.END)
                widget.insert(0, str(orb))

        if act_electrons := int(get_value('nActEl')):
            act_electrons += 2 * sum(inact_orbs)
            self.notebook.lucia_data['electrons'] = act_electrons + 2 * sum(inact_orbs)
            self.electrons_entry.insert(0, str(act_electrons))

        if lcsblk := get_value('LCSBLK'):
            self.notebook.lucia_data['lcsblk'] = int(lcsblk)

        if musymu_line_ind := find_line_ind('MUSYMU'):
            states_data = self.load_states_data(lines, musymu_line_ind + 1)
            self.states_table.put(states_data.T)

        if self.path_exists(self.LUCIA_SA_FILE):
            self.sa_var.set(True)
            self.show_sa()
            self.load_sa()

        self.get_outputs()

    @log_operation('loading LUCIA_SA')
    def load_sa(self) -> None:
        """Load the state-averaged configuration if it exists."""
        lines = self.read_file(self.LUCIA_SA_FILE, '*')

        find_line_ind = partial(self.find_line_ind, lines)
        get_value = partial(self.get_value_from_lines, lines)

        inact_orbs: list[int] = []
        if inact_str_list := get_value('Inash').split(','):
            inact_orbs = [int(i) for i in inact_str_list]

        act_orbs: list[int] = []
        if atc_str_list := get_value('GASSH', 2).split(','):
            act_orbs = [int(a) for a in atc_str_list]

        for row, list_orbs in enumerate([inact_orbs, act_orbs], start=1):
            for col, orb in enumerate(list_orbs, 1):
                widget = cast(
                    ttk.Entry,
                    self.get_widget_from_grid(self.sa_inact_act_orb_frame, row, col),
                )
                widget.delete(0, tk.END)
                widget.insert(0, str(orb))

        if act_electrons := int(get_value('nActEl')):
            act_electrons += 2 * sum(inact_orbs)
            self.sa_electrons_entry.delete(0, tk.END)
            self.sa_electrons_entry.insert(0, str(act_electrons))

        if st_ave_line_ind := find_line_ind('ST_AVE'):
            states_data = self.load_states_data(lines, st_ave_line_ind + 1, sa=True)
            self.sa_states_table.put(states_data.T)

    @log_operation('getting lucia outputs')
    def get_outputs(self) -> None:
        """Refresh cached energies and notify dependent pages of any changes."""

        def output_file(ind: str | int) -> Path:
            return Path(f'QC/LUCIA_BLKH_{ind}.{ind}')

        if not (states := cast(list[str], self.notebook.lucia_data['states'])):
            return

        states_array = np.array(states)

        if not self.path_exists(output_file(len(states))):
            return

        energies: list[str] = []
        if self.ssh_client:
            energies_str, _, _ = self.ssh_client.run_remote_command(
                f"""for n in {{1..{len(states)}}};
                  do sed -n '2p' "{self.controller.running_directory}/{output_file('$n')}"; done""",
            )

            energies = energies_str.strip().split('\n ')
        else:
            for state_ind in range(1, len(states) + 1):
                energy = self.read_file(output_file(state_ind))[1].strip()
                energies.append(energy)

        energies_array = np.array(energies, dtype=float)

        states_array = states_array[np.argsort(energies_array)]
        energies_array = energies_array[np.argsort(energies_array)]

        relative_energies_array = energies_array - energies_array[0]

        states = cast(list[str], states_array.tolist())
        energies = cast(list[str], energies_array.astype(str).tolist())
        relative_energies = cast(
            list[str],
            relative_energies_array.astype(str).tolist(),
        )

        self.notebook.lucia_data.update({
            'states': states,
            'energies': energies,
            'relative_energies': relative_energies,
        })

        cc_page: Clscplng = cast('Clscplng', self.notebook.pages[3])
        cc_page.show_lucia_output()

    def pack_all_sym(self, states_list: np.ndarray, sym_ind: int) -> np.ndarray:
        """Convert block with all symmetries to a single line with symmetry "all".

        Returns
        -------
        np.ndarray
            Updated array with combined symmetry entries.
        """
        counter: list[int] = [1]
        temp_list = [states_list[0]]

        slice_: list[int] = [i for i in range(states_list.shape[1]) if i != sym_ind]
        for item in states_list[1:]:
            flag = True
            for ind, temp_item in enumerate(temp_list):
                if np.array_equal(temp_item[slice_], item[slice_]):
                    temp_item[sym_ind] = f'{temp_item[sym_ind]},{item[sym_ind]}'
                    counter[ind] += 1
                    flag = False
                    break
            if flag:
                temp_list.append(item)
                counter.append(1)

        # After all states were added together, check if we have enough to make "all" symmetry
        result_list: list[list[str]] = []
        for temp_item, count in zip(temp_list, counter):
            if count == len(self.sym.irrep) - 1:
                temp_item[sym_ind] = 'ALL'
                result_list.append(cast(list[str], temp_item.tolist()))
            else:
                syms = temp_item[sym_ind].split(',')
                for sym in syms:
                    temp_item[sym_ind] = sym
                    result_list.append(cast(list[str], temp_item.tolist()))

        return np.array(result_list)

    def unpack_all_sym(self, states_list: np.ndarray, sym_ind: int) -> np.ndarray:
        """Convert "all" symmetry to all the symmetries in the group.

        Returns
        -------
        np.ndarray
            Array where each "ALL" entry is expanded into explicit irreps.
        """
        new_list: list[np.ndarray] = []
        for row in states_list:
            if row[sym_ind] == 'ALL':
                for sym in self.sym.irrep[1:]:
                    temp_row = row.copy()
                    temp_row[sym_ind] = sym
                    new_list.append(temp_row)
            else:
                new_list.append(row)

        return np.array(new_list)

    def get_states_data(
        self,
        sa: bool = False,
        active_electrons: int = 0,
    ) -> tuple[np.ndarray, str]:
        """Return validated state table data and the serialized block for lucia.

        Returns
        -------
        tuple[np.ndarray, str]
            Processed state data array and serialised string representation.
        """
        table = self.sa_states_table if sa else self.states_table
        states_data = table.get()
        logger.debug('States data type: %s', states_data.dtype)
        logger.debug('States data retrieved from table: %s', states_data)

        # Check for empty and partially filled rows
        # states_data is shape (num_columns, num_rows), so transpose to work with rows
        states_data_transposed = states_data.T
        rows_to_keep = []

        for row_idx, row in enumerate(states_data_transposed):
            # Check if row is completely empty
            row_empty = np.all(row == '')  # noqa: PLC1901
            # Check if row is completely filled (no empty strings)
            row_filled = np.all(row != '')  # noqa: PLC1901

            if row_empty:
                # Skip completely empty rows (automatically remove them)
                continue
            if not row_filled:
                # Partially filled row - warn user
                warning_popup(
                    'Some target state rows are partially filled. Please fill in all fields or remove the row.',
                )
                return np.array([]), ''
            # Fully filled row - keep it
            rows_to_keep.append(row_idx)

        # Filter to keep only fully filled rows
        if len(rows_to_keep) == 0:
            required_field_popup('target states')
            return np.array([]), ''

        states_data = states_data[:, rows_to_keep]

        sym_ind = 1 if sa else 0
        states_data = self.unpack_all_sym(states_data.T, sym_ind)

        if not sa:
            # Save the states list to the notebook cache
            self.notebook.lucia_data['states'] = self.get_states_list(states_data)
        else:
            # Format weights and add electrons and spin columns
            states_data = states_data.astype('U100')  # Allows for longer strings in the array
            states_data[:, 0] = np.array([f'{float(weight):e}'.replace('e', 'D') for weight in states_data[:, 0]])

            electrons_column = np.full(states_data.shape[0], active_electrons)
            states_data = np.insert(states_data, 3, electrons_column, axis=1)

            spin_column = states_data[:, 2].astype(int) - 1
            states_data = np.insert(states_data, 4, spin_column, axis=1)

        # Converts symmetry from string to index
        states_data[:, sym_ind] = np.array([self.sym.irrep.index(irrep) for irrep in states_data[:, sym_ind]])

        # Sorts the data based on the pattern lucia expects
        states_data = states_data[
            np.lexsort((states_data[:, sym_ind + 1], states_data[:, sym_ind])),
            :,
        ]

        if not sa:
            lines = [f'{states_data.shape[0]}'] + [' '.join(state) for state in states_data]
        else:
            lines = [f'{np.sum(states_data[:, -1].astype(int))}']
            for state in states_data:
                lines.extend([' '.join(state[:-1])] * int(state[-1]))

        return states_data, '\n'.join(lines)

    def get_inact_act(self, frame: ttk.Frame, row: int) -> list[int]:
        """Extract inactive or active orbital indices from the provided row.

        Returns
        -------
        list[int]
            Orbital indices gathered from the specified row.
        """
        orbs: list[int] = []
        for col in range(1, len(self.sym.irrep)):
            widget = cast(ttk.Entry, self.get_widget_from_grid(frame, row, col))
            if not (orb := self.get_text_from_widget(widget)):
                orb = '0'
            orbs.append(int(orb))
        return orbs

    def get_title(self) -> str:
        """Build the multi-line title passed to Lucia input files.

        Returns
        -------
        str
            Title block describing geometry, basis, and description.
        """
        title_lines = [
            self.notebook.molecule_data['geom_label'] or 'geometry',
            self.notebook.dalton_data['basis'] or 'basis',
            self.notebook.dalton_data['description'] or 'description',
        ]

        return '\n'.join(title_lines)

    def save(self) -> None:
        """Validate the Lucia form and update the associated input files."""

        @dataclass
        class LuciaRequiredFields(RequiredFields):
            electrons: int = 0

            electrons_widget: ttk.Entry = self.electrons_entry

        required_fields = LuciaRequiredFields()

        if not required_fields.check_fields():
            return

        inact_orbs = self.get_inact_act(self.inact_act_orb_frame, 1)
        act_orbs = self.get_inact_act(self.inact_act_orb_frame, 2)

        total_electrons = required_fields.electrons
        active_electrons = total_electrons - 2 * sum(inact_orbs)

        self.notebook.lucia_data['electrons'] = total_electrons
        self.notebook.lucia_data['total_orbitals'] = [str(i + a) for i, a in zip(inact_orbs, act_orbs)]

        states_data, musymu = self.get_states_data()
        if not musymu:
            return

        highest_mult = np.max(states_data[:, 1].astype('int'))
        max_number_roots = np.max(states_data[:, 2].astype('int'))

        commands = {
            'group': self.sym.group.upper(),
            'mults': highest_mult,
            'ms2': highest_mult - 1,
            'inactive': ','.join(str(orb) for orb in inact_orbs),
            'active': ','.join(str(orb) for orb in act_orbs),
            'electrons': active_electrons,
            'musymu': musymu,
            'ref_sym': self.notebook.dalton_data['state_sym'],
            'roots': max_number_roots + 1,
            'lcsblk': self.notebook.lucia_data['lcsblk'],
            'title': self.get_title(),
        }

        if self.sa_var.get():
            self.save_sa()
            commands['mofrlu'] = 'MOFRLU'
        else:
            self.remove_path(self.LUCIA_SA_FILE)

        if self.notebook.molecule_data['linear_molecule']:
            commands['lz2'] = 'LZ2'

        self.save_file(self.LUCIA_FILE, commands, '*', blank_lines=False)

    def save_sa(self) -> None:
        """Persist the state-averaged Lucia configuration to disk."""
        required_fields = [('electrons', self.sa_electrons_entry, int)]

        if not (required_field_values := self.check_field_entries(required_fields)):
            return

        inact_orbs = self.get_inact_act(self.sa_inact_act_orb_frame, 1)
        act_orbs = self.get_inact_act(self.sa_inact_act_orb_frame, 2)

        active_electrons = int(required_field_values['electrons']) - 2 * sum(inact_orbs)

        states_data, state_ave_states = self.get_states_data(sa=True, active_electrons=active_electrons)
        if not state_ave_states:
            return

        highest_mult = np.max(states_data[:, 2].astype('int'))

        commands = {
            'group': self.sym.group.upper(),
            'inactive': ','.join(str(orb) for orb in inact_orbs),
            'active': ','.join(str(orb) for orb in act_orbs),
            'electrons': active_electrons,
            'st_ave_states': state_ave_states,
            'ms2': highest_mult - 1,
            'title': self.get_title(),
        }

        self.save_file(self.LUCIA_SA_FILE, commands, '*', blank_lines=False)

    def print_irrep(self, new_sym: bool = False) -> None:
        """Rebuild widgets using the newly selected symmetry."""

        def remove_add_irrep(frame: ttk.Frame) -> None:
            """Remove old irrep and and new one to needed widgets in specific frame."""
            # Removes previous irrep
            for row in range(3):
                for col in range(1, 9):
                    if widget := self.get_widget_from_grid(frame, row, col):
                        widget.destroy()

            # Adds new irrep
            for col, irrep in enumerate(self.sym.irrep[1:], start=1):
                ttk.Label(frame, text=irrep).grid(row=0, column=col)
                for row in range(1, 3):
                    ttk.Entry(frame, width=5).grid(row=row, column=col)

        if not new_sym:
            return  # Skips whole process of replacing widgets if the symmetry is the same

        remove_add_irrep(self.inact_act_orb_frame)
        remove_add_irrep(self.sa_inact_act_orb_frame)

        self.states_table.add_combobox_values_list([self.sym.irrep])
        self.states_table.reset()

        self.sa_states_table.add_combobox_values_list([self.sym.irrep])
        self.sa_states_table.reset()

    def show_sa(self) -> None:
        """Show or hide the state-average widgets and sync default values."""
        if self.sa_var.get():
            self.middle_screen.pack(side=tk.LEFT, before=self.right_screen, fill=tk.BOTH, expand=True, padx=10)
            self.sa_electrons_entry.delete(0, tk.END)
            self.sa_electrons_entry.insert(0, self.electrons_entry.get())

            # Gets the inact/act orbs from left screen and adds them to the middle
            for row in range(1, 3):
                for col in range(1, len(self.sym.irrep)):
                    widget = cast(
                        ttk.Entry,
                        self.get_widget_from_grid(self.inact_act_orb_frame, row, col),
                    )
                    orb = self.get_text_from_widget(widget)

                    sa_widget = cast(
                        ttk.Entry,
                        self.get_widget_from_grid(
                            self.sa_inact_act_orb_frame,
                            row,
                            col,
                        ),
                    )
                    sa_widget.delete(0, tk.END)
                    sa_widget.insert(0, orb)
        else:
            self.middle_screen.pack_forget()

    def erase(self) -> None:
        """Reset the Lucia UI and cached state."""
        self.print_irrep(new_sym=True)

        self.electrons_entry.delete(0, tk.END)
        self.sa_electrons_entry.delete(0, tk.END)

        self.sa_var.set(False)
        self.show_sa()

        for item in self.orbs_tv.get_children():
            self.orbs_tv.delete(item)
