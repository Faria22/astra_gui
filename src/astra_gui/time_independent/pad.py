"""Notebook page that configures PAD (photoelectron angular distribution) runs."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from astra_gui.utils.popup_module import missing_required_calculation_popup, required_field_popup

from .ti_notebook_page_module import TiNotebookPage

if TYPE_CHECKING:
    from .time_independent_notebook import TimeIndependentNotebook


class Pad(TiNotebookPage):
    """Configure and run PAD calculations for time-independent workflows."""

    SCRIPT_FILE = Path('run_pad.sh')
    SCRIPT_COMMANDS = ['astraPAD']

    def __init__(self, notebook: 'TimeIndependentNotebook') -> None:
        """Initialise the PAD page and its default widgets."""
        super().__init__(notebook, 'Photoionization PT1')

    def left_screen_def(self) -> None:
        """Build the controls for gauge, reference frame, and symmetry."""
        gauge_frame = ttk.Frame(self.left_screen, borderwidth=1, relief='solid')
        gauge_frame.grid(row=0, column=0, padx=5, pady=5, rowspan=3)

        ttk.Label(gauge_frame, text='Gauge').grid(row=0, column=0, columnspan=2)
        ttk.Label(gauge_frame, text='Length:').grid(row=1, column=0)
        ttk.Label(gauge_frame, text='Velocity:').grid(row=2, column=0)

        self.gauge_vars = []
        for i in range(2):
            self.gauge_vars.append(tk.BooleanVar(value=False))
            ttk.Checkbutton(gauge_frame, variable=self.gauge_vars[i]).grid(row=i + 1, column=1)

        ket_sym_hover_text = """Multiplicity and symmetry of ket state (comma separated list).\n
                                If all symmetries of the group are desired, {Mult}ALL can be used instead."""
        self.hover_widget(ttk.Label, self.left_screen, text='Ket Symmetry', hover_text=ket_sym_hover_text).grid(
            row=0,
            column=1,
            padx=5,
        )
        self.ket_sym_entry = ttk.Entry(self.left_screen, width=5)
        self.ket_sym_entry.grid(row=1, column=1, padx=5)

        self.hover_widget(
            ttk.Label,
            self.left_screen,
            text='State index:',
            hover_text='What eigenstate will be used for the bound state',
        ).grid(row=0, column=2)
        self.state_entry = ttk.Entry(self.left_screen, width=5)
        self.state_entry.grid(row=1, column=2, padx=5)

        mode_frame = ttk.Frame(self.left_screen, borderwidth=1, relief='solid')
        mode_frame.grid(row=0, column=3, padx=5, pady=5, rowspan=3)

        ttk.Label(mode_frame, text='Reference Frame').grid(row=0, column=0, columnspan=2)
        ttk.Label(mode_frame, text='Lab:').grid(row=1, column=0)
        ttk.Label(mode_frame, text='Molecular:').grid(row=2, column=0)

        self.mode_vars = []
        for i in range(2):
            self.mode_vars.append(tk.BooleanVar(value=False))
            if i == 1:
                ttk.Checkbutton(mode_frame, variable=self.mode_vars[i], command=self.show_mfpad).grid(
                    row=i + 1,
                    column=1,
                )
            else:
                ttk.Checkbutton(mode_frame, variable=self.mode_vars[i]).grid(row=i + 1, column=1)

        self.mfpad_frame = ttk.Frame(self.left_screen)
        ttk.Label(self.mfpad_frame, text='MFPAD input file').grid(row=0, column=0)
        self.mfpad_file_entry = ttk.Entry(self.mfpad_frame)
        self.mfpad_file_entry.grid(row=1, column=0)

        self.show_mfpad()

        self.save_button.grid(row=4, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=5, column=0)

    def show_mfpad(self) -> None:
        """Toggle the additional inputs required for molecular-frame PAD."""
        if self.mode_vars[1].get():
            self.mfpad_frame.grid(row=0, column=4, rowspan=3, padx=5, pady=5)
        else:
            self.mfpad_frame.grid_forget()

    def erase(self) -> None:
        """Reset the PAD configuration widgets to their defaults."""
        self.erase_cc_data()

        for var in self.gauge_vars:
            var.set(False)

        self.ket_sym_entry.delete(0, tk.END)
        self.state_entry.delete(0, tk.END)

    def get_commands(self) -> str:
        """Create the list of PAD commands based on current selections.

        Returns
        -------
        str
            Concatenated shell commands ready to run.
        """
        if not (ket_sym := self.get_text_from_widget(self.ket_sym_entry)):
            required_field_popup('Ket symmetry')
            return ''

        if not self.check_ket_sym(ket_sym):
            return ''

        ket_syms = ket_sym.split(',')
        for ket_sym in ket_syms:
            ket_sym_path = self.sym.convert_cs_irreps_to_letter(ket_sym)
            if not self.path_exists(
                Path(f'store/CloseCoupling/{ket_sym_path}/Full/Scattering_States'),
            ):
                missing_required_calculation_popup('Scattering States')
                return ''

        if not (state := self.get_text_from_widget(self.state_entry)):
            required_field_popup('State index')
            return ''

        lines = []

        if not any(var.get() for var in self.gauge_vars):
            required_field_popup('Gauge')
            return ''

        if not any(var.get() for var in self.mode_vars):
            required_field_popup('Reference frame')
            return ''

        for mode_var, mode in zip(self.mode_vars, ['lfpad', 'mfpad']):
            if mode_var.get():
                mfpad_str = ''

                if mode == 'mfpad':
                    if not (mfpad_file := self.get_text_from_widget(self.mfpad_file_entry)):
                        required_field_popup('MFPAD input file path')
                        return ''

                    mfpad_str = f'-padif {mfpad_file} --onlycoeff'

                for gauge, gauge_var in zip(['l', 'v'], self.gauge_vars):
                    if gauge_var.get():
                        lines.append(
                            f'astraPAD -gif ASTRA.INP -ketsym {ket_sym} -state {state} -gauge {gauge} {mfpad_str}',
                        )

        return self.add_idle_thread_and_join_lines(lines)

    def load(self) -> None:
        """Populate the PAD form using the saved script."""
        lines = self.get_script_lines()

        if not lines:
            return

        ket_sym = self.get_keyword_from_line(lines[0], '-ketsym')
        state = self.get_keyword_from_line(lines[0], '-state')

        self.ket_sym_entry.insert(0, ket_sym)
        self.state_entry.insert(0, state)

        for line in lines:
            gauge = self.get_keyword_from_line(line, '-gauge')

            if gauge == 'l':
                self.gauge_vars[0].set(True)
            elif gauge == 'v':
                self.gauge_vars[1].set(True)

            if '-padif' in line:
                self.mode_vars[1].set(True)
                mfpad_file = self.get_keyword_from_line(line, '-padif')
                self.mfpad_file_entry.delete(0, tk.END)
                self.mfpad_file_entry.insert(0, mfpad_file)
            else:
                self.mode_vars[0].set(True)

    def get_outputs(self) -> None:
        """PAD does not expose additional outputs through the GUI yet."""
