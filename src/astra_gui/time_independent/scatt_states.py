"""Notebook page that configures scattering-state calculations."""

import bisect
import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

import numpy as np

from astra_gui.utils.popup_module import invalid_input_popup, missing_required_calculation_popup, required_field_popup

from .ti_notebook_page_module import TiNotebookPage

if TYPE_CHECKING:
    from .time_independent_notebook import TimeIndependentNotebook


logger = logging.getLogger(__name__)


class ScattStates(TiNotebookPage):
    """Notebook page for running scattering-state computations."""

    SCRIPT_FILE = Path('run_scatt_states.sh')
    SCRIPT_COMMANDS = ['astraComputeScattStates']
    DISABLED_ENTRY_TEXT = 'Disabled'

    def __init__(self, notebook: 'TimeIndependentNotebook') -> None:
        super().__init__(notebook, 'Scattering States')

    def left_screen_def(self) -> None:
        """Create widgets for configuring the scattering-state calculation."""
        # min/max energy
        energy_frame = ttk.Frame(self.left_screen)
        energy_frame.grid(row=0, column=0, columnspan=10, sticky='w')

        ttk.Label(energy_frame, text='Minimum Energy [au]:').grid(row=0, column=0)
        self.min_e_entry = ttk.Entry(energy_frame, width=10)
        self.min_e_entry.grid(row=0, column=1, padx=5)

        ttk.Label(energy_frame, text='Maximum Energy [au]:').grid(row=0, column=2)
        self.max_e_entry = ttk.Entry(energy_frame, width=10)
        self.max_e_entry.grid(row=0, column=3, padx=5)

        # min/max thrs
        thrs_frame = ttk.Frame(self.left_screen)
        thrs_frame.grid(row=1, column=0, columnspan=10, sticky='w')
        self.hover_widget(
            ttk.Label,
            thrs_frame,
            text='Minimum Threshold:',
            hover_text='Threshold number as defined in the CC basis',
        ).grid(row=0, column=0)
        self.min_thrs_entry = ttk.Entry(thrs_frame, width=10)
        self.min_thrs_entry.grid(row=0, column=1, padx=5)

        self.hover_widget(
            ttk.Label,
            thrs_frame,
            text='Maximum Threshold:',
            hover_text='Threshold number as defined in the CC basis',
        ).grid(row=0, column=2)
        self.max_thrs_entry = ttk.Entry(thrs_frame, width=10)
        self.max_thrs_entry.grid(row=0, column=3, padx=5)

        self.min_e_entry.bind('<KeyRelease>', lambda event: self.toggle_entries(event, self.min_thrs_entry))
        self.min_thrs_entry.bind('<KeyRelease>', lambda event: self.toggle_entries(event, self.min_e_entry))
        self.max_e_entry.bind('<KeyRelease>', lambda event: self.toggle_entries(event, self.max_thrs_entry))
        self.max_thrs_entry.bind('<KeyRelease>', lambda event: self.toggle_entries(event, self.max_e_entry))

        # Energy difference
        de_frame = ttk.Frame(self.left_screen)
        de_frame.grid(row=2, column=0, columnspan=10, sticky='w')
        self.hover_widget(
            ttk.Label,
            de_frame,
            text='Energy difference between points [au]:',
            hover_text='If left blank, default value is 0.01au',
        ).grid(row=0, column=0)
        self.de_entry = ttk.Entry(de_frame, width=5)
        self.de_entry.grid(row=0, column=1, padx=5)

        # Degeneracy tolerance
        self.hover_widget(
            ttk.Label,
            de_frame,
            text='Max degeneracy gap:',
            hover_text='Maximum energy gap between degenerate thresholds.\nIf left blank, default value is 1e-10 au',
        ).grid(row=0, column=2)
        self.deg_tol_entry = ttk.Entry(de_frame, width=5)
        self.deg_tol_entry.grid(row=0, column=3, padx=5)
        self.deg_tol_entry.bind('<KeyRelease>', self.change_target_states_index)

        self.refine_frame = ttk.Frame(self.left_screen)
        self.refine_frame.grid(row=3, column=0, columnspan=10, sticky='w')
        self.hover_widget(
            ttk.Label,
            self.refine_frame,
            text='Refine energy grid:',
            hover_text='Resolves the energy grid around the resonances.',
        ).grid(row=0, column=0)
        self.refine_var = tk.BooleanVar(value=True)
        refine_button = ttk.Checkbutton(self.refine_frame, variable=self.refine_var, command=self.show_refine_option)
        refine_button.grid(row=0, column=1)

        self.phase_frame = ttk.Frame(self.left_screen)
        self.hover_widget(
            ttk.Label,
            self.phase_frame,
            text='Maximum change in phase:',
            hover_text='If left blank, default value is 0.1',
        ).grid(row=0, column=0)
        self.dph_entry = ttk.Entry(self.phase_frame, width=5)
        self.dph_entry.grid(row=0, column=1, padx=5)

        # Ket Sym
        sym_frame = ttk.Frame(self.left_screen)
        sym_frame.grid(row=5, column=0, columnspan=10, sticky='w')
        ket_sym_hover_text = """Multiplicity and symmetry of ket state (comma separated list).\n
                                If all symmetries of the group are desired, {Mult}ALL can be used instead."""
        self.hover_widget(ttk.Label, sym_frame, text='Ket Symmetry:', hover_text=ket_sym_hover_text).grid(
            row=0,
            column=0,
        )
        self.ket_sym_entry = ttk.Entry(sym_frame, width=5)
        self.ket_sym_entry.grid(row=0, column=1, padx=5)

        # Overwrite
        self.hover_widget(
            ttk.Label,
            self.left_screen,
            text='Overwrite:',
            hover_text='Overwrite previous scattering state calculation results.',
        ).grid(row=6, column=0)
        self.overwrite_var = tk.BooleanVar(value=True)
        overwrite_checkbutton = ttk.Checkbutton(self.left_screen, variable=self.overwrite_var)
        overwrite_checkbutton.grid(row=6, column=1)

        self.save_button.grid(row=7, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=8, column=0)

    def show_refine_option(self) -> None:
        """Show or hide the refinement parameters based on the checkbox."""
        if self.refine_var.get():
            self.phase_frame.grid(row=4, column=0, columnspan=10, sticky='w')
        else:
            self.phase_frame.grid_forget()

    def change_target_states_index(self, _event: tk.Event | None = None) -> None:
        """Update the numbering of target states based on degeneracy tolerance."""
        if (deg_tol := self.get_deg_tol(show_popup=False)) == -1:
            return

        index = 1
        prev_energy = 0
        for state_ind, iid in enumerate(self.target_states_tv.get_children()):
            values = self.target_states_tv.item(iid)['values']
            energy = float(values[-2])

            if state_ind != 0 and np.abs(prev_energy - energy) < deg_tol:
                temp_ind = ''
            else:
                temp_ind = str(index)
                index += 1

            self.target_states_tv.item(iid, values=(temp_ind, *values[1:]))
            prev_energy = energy

    @staticmethod
    def toggle_entries(event: tk.Event, disable_entry: ttk.Entry) -> None:
        """Disable the paired entry when a value is provided."""
        assert isinstance(event.widget, ttk.Entry)

        if event.widget.get():
            disable_entry.insert(0, ScattStates.DISABLED_ENTRY_TEXT)
            disable_entry.configure(state='disabled')
        else:
            disable_entry.config(state='normal')
            disable_entry.delete(0, tk.END)

    def toggle_all_entries(self) -> None:
        """Sync enable/disable states based on which fields contain values."""
        self.min_e_entry.config(state='normal')
        self.min_thrs_entry.config(state='normal')
        self.max_e_entry.config(state='normal')
        self.max_thrs_entry.config(state='normal')

        if self.get_text_from_widget(self.min_e_entry):
            self.min_thrs_entry.insert(0, self.DISABLED_ENTRY_TEXT)
            self.min_thrs_entry.configure(state='disabled')
        elif self.get_text_from_widget(self.min_thrs_entry):
            self.min_e_entry.insert(0, self.DISABLED_ENTRY_TEXT)
            self.min_e_entry.configure(state='disabled')

        if self.get_text_from_widget(self.max_e_entry):
            self.max_thrs_entry.insert(0, self.DISABLED_ENTRY_TEXT)
            self.max_thrs_entry.configure(state='disabled')
        elif self.get_text_from_widget(self.max_thrs_entry):
            self.max_e_entry.insert(0, self.DISABLED_ENTRY_TEXT)
            self.max_e_entry.configure(state='disabled')

    def erase(self) -> None:
        """Reset the form to its default state."""
        self.erase_cc_data()

        self.min_e_entry.config(state='normal')
        self.min_thrs_entry.config(state='normal')
        self.max_e_entry.config(state='normal')
        self.max_thrs_entry.config(state='normal')

        self.min_e_entry.delete(0, tk.END)
        self.max_e_entry.delete(0, tk.END)
        self.min_thrs_entry.delete(0, tk.END)
        self.max_thrs_entry.delete(0, tk.END)

        self.de_entry.delete(0, tk.END)
        self.deg_tol_entry.delete(0, tk.END)

        self.refine_var.set(True)
        self.show_refine_option()
        self.dph_entry.delete(0, tk.END)

        self.ket_sym_entry.delete(0, tk.END)

    def get_commands(self) -> str:
        """Assemble the command sequence for scattering-state calculations.

        Returns
        -------
        str
            Commands joined by newlines; empty string when validation fails.
        """
        def find_threshold(min_e: float, max_e: float) -> tuple[int | None, ...]:
            """
            Return the lowest and highest threshold inside a given energy range.

            If None, None is returned, there are no thresholds in the given range.
            if -1, -1 is returned, the input is invalid.

            Returns
            -------
            tuple[int | None, ...]
                Tuple containing the minimum and maximum threshold indices.

            """
            if min_e < energies[0]:
                invalid_input_popup("'Minimum energy' is smaller than the energy of the first threshold.")
                return -1, -1

            if min_e > energies[-1]:
                return None, None

            min_thrs = bisect.bisect_left(energies, min_e) + 1
            max_thrs = bisect.bisect_right(energies, max_e)

            if energies[min_thrs - 1] > max_e:
                min_thrs = None
            if max_thrs <= min_e:
                max_thrs = None

            return min_thrs, max_thrs

        def interval_str(
            min_e: float | None = None,
            max_e: float | None = None,
            min_thrs: int | None = None,
            max_thrs: int | None = None,
        ) -> str:
            line = ''
            if min_e:
                line = f'-emin {min_e}'
            elif min_thrs:
                line = f'-thrmin {min_thrs}'
            else:
                logger.error('No minimum energy/threshold provided for interval.')

            if max_e:
                return f'{line} -emax {max_e}'
            if max_thrs:
                return f'{line} -thrmax {max_thrs}'

            logger.error('No maximum energy/threshold provided for interval.')
            return ''

        def write_intervals(
            min_e: float | None = None,
            max_e: float | None = None,
            min_thrs: int | None = None,
            max_thrs: int | None = None,
        ) -> list[str]:
            lines = []
            if (min_thrs and max_thrs) and max_thrs - min_thrs > 1:
                for t in range(min_thrs, max_thrs):
                    lines.extend(write_intervals(min_thrs=t, max_thrs=t + 1))
            else:
                str_interval = interval_str(min_e, max_e, min_thrs, max_thrs)
                lines.append(f'{base_command} uniform {str_interval} -dEmax {de}')
                if refine:
                    lines.extend([
                        f'{base_command} rydberg {str_interval} -pqnmin 1 -pqnmax 7',
                        f'{base_command} resolve {str_interval}',
                        f'{base_command} refine {str_interval} -dPhmax {dph}',
                    ])
                    # Remove the last two lines if the maximum energy is above the last threshold
                    if max_e is not None and max_e > energies[-1]:
                        lines.pop(-3)
                        lines.pop(-1)

            return lines

        ket_sym = self.get_text_from_widget(self.ket_sym_entry).replace(' ', '')
        if not ket_sym:
            required_field_popup('Ket symmetry')
            return ''

        if not self.check_ket_sym(ket_sym):
            return ''

        ket_syms = self.unpack_all_symmetry(ket_sym.split(','))
        for ket_sym in ket_syms:
            ket_sym_path = self.sym.convert_cs_irreps_to_letter(ket_sym)
            if not self.path_exists(
                Path(f'store/CloseCoupling/{ket_sym_path}/Full/H_Fullc_Fullc_eval'),
            ):
                missing_required_calculation_popup('Diagonalization')
                return ''

        ket_sym = ','.join(self.pack_all_symmetry(ket_syms))

        de = self.get_text_from_widget(self.de_entry)
        if not de:
            de = 0.01

        try:
            de = float(de)
        except ValueError:
            invalid_input_popup(
                "'Energy difference between points' must be a real value.",
            )
            return ''

        deg_tol = self.get_deg_tol()
        if deg_tol == -1:
            return ''

        energies = self.get_state_energies()

        if not energies:
            missing_required_calculation_popup('CC file and Lucia')
            return ''

        dph = 0
        refine = self.refine_var.get()
        if refine:
            dph = self.get_text_from_widget(self.dph_entry)
            if not dph:
                dph = 0.1

            try:
                dph = float(dph)
            except ValueError:
                invalid_input_popup("'Maximum change in phase' must be a real value.")
                return ''

        labels = ['Minimum energy', 'Maximum energy', 'Minimum threshold', 'Maximum threshold']
        entries = [self.min_e_entry, self.max_e_entry, self.min_thrs_entry, self.max_thrs_entry]
        types = [float, float, int, int]

        values = []
        for label, entry, type_ in zip(labels, entries, types):
            value = self.get_text_from_widget(entry)
            if value and value != self.DISABLED_ENTRY_TEXT:
                try:
                    values.append(type_(value))
                except ValueError:
                    invalid_input_popup(f"'{label}' must be a {type_.__name__} value")
                    return ''
            else:
                values.append(0)

        base_command = (
            f'astraComputeScattStates -gif ASTRA.INP -sym {ket_sym} -degtol {str(deg_tol).replace("e", "d")} --bf -mode'
        )
        lines = []

        min_e, max_e, min_thrs, max_thrs = values

        # User used both min_e and max_e
        if all(val for val in (min_e, max_e)):
            if max_e <= min_e:
                invalid_input_popup(
                    "'Minimum energy' must be smaller than 'Maximum energy'.",
                )
                return ''

            min_thrs, max_thrs = find_threshold(min_e, max_e)

            if min_thrs == -1:  # Invalid input
                return ''

            if min_thrs:
                lines.extend(write_intervals(min_e=min_e, max_thrs=min_thrs))
                if max_thrs:
                    lines.extend(write_intervals(min_thrs=min_thrs, max_thrs=max_thrs))
                    lines.extend(write_intervals(min_thrs=max_thrs, max_e=max_e))
                else:
                    lines.extend(write_intervals(min_thrs=min_thrs, max_e=max_e))
            else:
                lines.extend(write_intervals(min_e=min_e, max_e=max_e))

        # User used both min_thrs and max_thrs
        elif all(val for val in (min_thrs, max_thrs)):
            if max_thrs > len(energies):
                invalid_input_popup("'Maximum threshold' is larger than the total number of non degenerate thresholds.")
                return ''

            if min_thrs >= max_thrs:
                invalid_input_popup("'Minimum threshold' needs to be larger than 'Maximum threshold'.")
                return ''

            lines.extend(write_intervals(min_thrs=min_thrs, max_thrs=max_thrs))

        # User used min_e and max_thrs
        elif all(val for val in (min_e, max_thrs)):
            if energies[max_thrs - 1] <= min_e:
                invalid_input_popup(
                    "'Minimum energy' must be smaller than the energy of the maximum threshold.",
                )
                return ''

            if max_thrs > len(energies):
                invalid_input_popup(
                    "'Maximum threshold' is larger than the total number of thresholds.",
                )
                return ''

            min_thrs, max_thrs = find_threshold(min_e, energies[max_thrs - 1])
            if min_thrs == -1:
                return ''

            if min_thrs:
                lines.extend(write_intervals(min_e=min_e, max_thrs=min_thrs))
                lines.extend(write_intervals(min_thrs=min_thrs, max_thrs=max_thrs))
            else:
                lines.extend(write_intervals(min_e=min_e, max_thrs=max_thrs))

        # User used min_thrs and max_e
        elif all(val for val in (min_thrs, max_e)):
            energies_of_min_thrs = energies[min_thrs - 1]
            if max_e <= energies_of_min_thrs:
                invalid_input_popup("'Maximum energy' must be larger than the energy of the minimum threshold.")
                return ''

            min_thrs, max_thrs = find_threshold(energies[min_thrs - 1], max_e)
            if min_thrs == -1:
                logger.error("'Minimum threshold' is larger than the maximum energy.")
                return ''

            if not (max_thrs and min_thrs):
                logger.error('No minimum or maximum threshold provided for interval.')
                return ''

            if max_thrs != min_thrs:
                lines.extend(write_intervals(min_thrs=min_thrs, max_thrs=max_thrs))
                lines.extend(write_intervals(min_thrs=max_thrs, max_e=max_e))
            else:
                lines.extend(write_intervals(min_thrs=min_thrs, max_e=max_e))

        if self.overwrite_var:
            lines[0] += ' --overwrite'

        return self.add_idle_thread_and_join_lines(lines)

    def get_deg_tol(self, show_popup: bool = True) -> float:
        """Return the degeneracy tolerance, optionally raising validation popups.

        Returns
        -------
        float
            Degeneracy tolerance value, or ``-1`` when invalid.
        """
        deg_tol = self.get_text_from_widget(self.deg_tol_entry)
        if not deg_tol:
            deg_tol = 1e-10

        try:
            deg_tol = float(deg_tol)
        except ValueError:
            if show_popup:
                invalid_input_popup("'Max degeneracy gap' must be a real value.")
            return -1
        else:
            return deg_tol

    def get_state_energies(self) -> list[float]:
        """Return the list of non-degenerate target-state energies.

        Returns
        -------
        list[float]
            Energies corresponding to unique thresholds.
        """
        thrs = self.get_deg_tol()
        if thrs == -1:
            return []

        energies = []

        prev_energy = np.inf
        for n, iid in enumerate(self.target_states_tv.get_children()):
            energy = float(self.target_states_tv.item(iid, 'values')[2])

            relative_energy = energy - prev_energy
            tag = self.target_states_tv.item(iid, 'tags')
            if (relative_energy < thrs and n > 0) or tag == ('disabled',):
                continue

            energies.append(energy)
            prev_energy = energy

        return energies

    def load(self) -> None:
        """Load scattering-state parameters from the saved script."""
        lines = self.get_script_lines()

        if not lines:
            return

        if (keyword := '-degtol') in lines[0]:
            deg_tol = self.get_keyword_from_line(lines[0], keyword)
            self.deg_tol_entry.insert(0, deg_tol.replace('d', 'e'))

        if (keyword := '-emin') in lines[0]:
            e_min = self.get_keyword_from_line(lines[0], keyword)
            self.min_e_entry.insert(0, e_min)
        elif (keyword := '-thrmin') in lines[0]:
            thrs_min = self.get_keyword_from_line(lines[0], keyword)
            self.min_thrs_entry.insert(0, thrs_min)

        if (keyword := '-emax') in lines[-1]:
            e_max = self.get_keyword_from_line(lines[-1], keyword)
            self.max_e_entry.insert(0, e_max)
        elif (keyword := '-thrmax') in lines[-1]:
            thrs_max = self.get_keyword_from_line(lines[-1], keyword)
            self.max_thrs_entry.insert(0, thrs_max)

        de = self.get_keyword_from_line(lines[0], '-dEmax')
        self.de_entry.insert(0, de)

        for line in lines:
            if 'refine' in line:
                dph = self.get_keyword_from_line(line, '-dPhmax')
                self.dph_entry.insert(0, dph)
                break

        sym = self.get_keyword_from_line(lines[0], '-sym')
        self.ket_sym_entry.insert(0, sym)

        self.toggle_all_entries()
        self.change_target_states_index()

    def get_outputs(self) -> None:
        """Refresh derived outputs (not yet implemented)."""
