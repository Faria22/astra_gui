"""UI logic for configuring structural time-independent calculations."""

import logging
import tkinter as tk
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from astra_gui.utils.font_module import bold_font
from astra_gui.utils.popup_module import (
    messagebox,
    missing_required_calculation_popup,
    missing_symmetry_popup,
    required_field_popup,
)

from .ti_notebook_page_module import TiNotebookPage

if TYPE_CHECKING:
    from .time_independent_notebook import TimeIndependentNotebook

logger = logging.getLogger(__name__)


class Structural(TiNotebookPage):
    """Notebook page that manages structural calculations and operators."""

    SCRIPT_FILE = Path('run_structural.sh')
    SCRIPT_COMMANDS = [
        'astraBuildOperator',
        'astraCondition',
        'astraDipoleTransition',
        'astraSusceptibility',
    ]

    def __init__(self, notebook: 'TimeIndependentNotebook') -> None:
        super().__init__(notebook, 'Structural', show_cap_radii=True)

    def left_screen_def(self) -> None:
        """Build the primary panels used for structural inputs."""
        self.operators()
        self.dipoles()
        self.susceptibility()
        self.diag_hamiltonian()

        self.save_button.grid(row=4, column=0, pady=self.SAVE_BUTTON_PADY)
        self.run_button.grid(row=5, column=0)

    def operators(self) -> None:
        """Lay out the operator selection widgets."""
        operators_frame = ttk.Frame(self.left_screen)
        operators_frame.grid(row=0, column=0, columnspan=10, pady=10, sticky='w')
        ttk.Label(operators_frame, text='Symmetric Operators:', font=bold_font).grid(row=0, column=0, padx=5, rowspan=2)
        self.op_labels = ['S', 'H', 'CAP', 'MASK']
        self.op_vars = [tk.BooleanVar(value=False) for _ in self.op_labels]
        for ind, op in enumerate(self.op_labels, 1):
            self.op_vars.append(tk.BooleanVar(value=False))
            ttk.Label(operators_frame, text=op).grid(row=0, column=ind, padx=5)
            ttk.Checkbutton(operators_frame, variable=self.op_vars[ind - 1]).grid(row=1, column=ind)

        self.hover_widget(ttk.Label, operators_frame, text='State Symmetry', hover_text=self.KET_SYM_HOVER_TEXT).grid(
            row=0,
            column=5,
            padx=5,
        )
        self.op_ket_sym_entry = ttk.Entry(operators_frame, width=5)
        self.op_ket_sym_entry.grid(row=1, column=5, padx=5)

    def dipoles(self) -> None:
        """Lay out the dipole selection widgets."""
        dipoles_frame = ttk.Frame(self.left_screen)
        dipoles_frame.grid(row=1, column=0, pady=10, columnspan=10, sticky='w')
        ttk.Label(dipoles_frame, text='Dipoles:', font=bold_font).grid(row=0, column=0, padx=5, rowspan=3)

        length_frame = ttk.Frame(dipoles_frame, borderwidth=1, relief='solid')
        velocity_frame = ttk.Frame(dipoles_frame, borderwidth=1, relief='solid')

        for ind, f in enumerate([length_frame, velocity_frame], 1):
            f.grid(row=0, column=ind, padx=5, rowspan=3)

        ttk.Label(length_frame, text='Length').grid(row=0, column=0, columnspan=3)
        ttk.Label(velocity_frame, text='Velocity').grid(row=0, column=0, columnspan=3)

        self.dp_labels = ['x', 'y', 'z', 'dx', 'dy', 'dz']
        self.dp_vars = [tk.BooleanVar(value=False) for _ in self.dp_labels]
        for ind, label in enumerate(self.dp_labels[:3]):
            ttk.Label(length_frame, text=label).grid(row=1, column=ind)
            ttk.Checkbutton(length_frame, variable=self.dp_vars[ind]).grid(row=2, column=ind)

        for ind, label in enumerate(self.dp_labels[3:]):
            ttk.Label(velocity_frame, text=label).grid(row=1, column=ind)
            ttk.Checkbutton(velocity_frame, variable=self.dp_vars[ind + 3]).grid(row=2, column=ind)

        self.hover_widget(ttk.Label, dipoles_frame, text='Ket Symmetry', hover_text=self.KET_SYM_HOVER_TEXT).grid(
            row=0,
            column=7,
            padx=5,
        )
        self.dp_ket_sym_entry = ttk.Entry(dipoles_frame, width=5)
        self.dp_ket_sym_entry.grid(row=1, column=7, padx=5)

    def diag_hamiltonian(self) -> None:
        """Build controls for diagonalising the Hamiltonian."""
        h_frame = ttk.Frame(self.left_screen)
        h_frame.grid(row=2, column=0, pady=10, columnspan=10, sticky='w')
        ttk.Label(h_frame, text='Diagonalize the Hamiltonian:', font=bold_font).grid(row=0, column=0, padx=5, rowspan=3)

        ttk.Label(h_frame, text='Real').grid(row=0, column=1, padx=5)
        self.real_h_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(h_frame, variable=self.real_h_var).grid(row=0, column=2)

        ttk.Label(h_frame, text='CAP').grid(row=1, column=1, padx=5)
        self.complex_h_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(h_frame, variable=self.complex_h_var, command=self.show_h_cap_widgets).grid(
            row=1,
            column=2,
            padx=5,
        )

        ttk.Label(h_frame, text='ECS').grid(row=2, column=1, padx=5)
        self.ecs_h_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(h_frame, variable=self.ecs_h_var, command=self.show_h_ecs_widgets).grid(row=2, column=2, padx=5)

        self.hover_widget(ttk.Label, h_frame, text='State Symmetry', hover_text=self.KET_SYM_HOVER_TEXT).grid(
            row=0,
            column=3,
            padx=5,
        )
        self.h_ket_sym_entry = ttk.Entry(h_frame, width=5)
        self.h_ket_sym_entry.grid(row=1, column=3, padx=5)

        # CAPs' strengths
        self.h_cap_frame = ttk.Frame(h_frame, borderwidth=1, relief='solid')
        ttk.Label(self.h_cap_frame, text='CAP strength(s):').grid(row=0, column=0, columnspan=2)
        self.h_cap_entries = []
        for ind in range(2):
            ttk.Label(self.h_cap_frame, text=f'CAP {ind + 1}').grid(row=1, column=ind, padx=5)
            e = ttk.Entry(self.h_cap_frame, width=10)
            e.grid(row=2, column=ind, padx=5)
            self.h_cap_entries.append(e)

        self.show_h_cap_widgets()

        # ECS parameters
        self.h_ecs_frame = ttk.Frame(h_frame, borderwidth=1, relief='solid')
        ttk.Label(self.h_ecs_frame, text='ECS Parameters').grid(row=0, column=0, columnspan=2)
        self.h_ecs_entries = []
        ecs_params = ['Radius', 'Angle']
        for ind in range(2):
            ttk.Label(self.h_ecs_frame, text=f'{ecs_params[ind]}').grid(row=1, column=ind, padx=5)
            e = ttk.Entry(self.h_ecs_frame, width=6)
            e.grid(row=2, column=ind, padx=5)
            self.h_ecs_entries.append(e)

        self.show_h_ecs_widgets()

    def show_h_cap_widgets(self) -> None:
        """Toggle the CAP panels for Hamiltonian diagonalisation."""
        if self.complex_h_var.get():
            self.h_cap_frame.grid(row=0, column=4, rowspan=3, padx=5)

            if self.complex_susc_var.get():
                self.susc_cap_frame.grid_forget()
        else:
            self.h_cap_frame.grid_forget()

            if self.complex_susc_var.get():
                self.susc_cap_frame.grid(row=0, column=5, rowspan=3)

    def show_h_ecs_widgets(self) -> None:
        """Toggle the ECS parameter inputs for the Hamiltonian block."""
        if self.ecs_h_var.get():
            self.h_ecs_frame.grid(row=0, column=5, rowspan=3, padx=5)
        else:
            self.h_ecs_frame.grid_forget()

    def susceptibility(self) -> None:
        """Build the susceptibility block for selecting operators and options."""
        susc_frame = ttk.Frame(self.left_screen)
        susc_frame.grid(row=3, column=0, pady=10, columnspan=10, sticky='w')
        self.hover_widget(ttk.Label, susc_frame, text='Susceptibility:', font=bold_font).grid(
            row=0,
            column=0,
            padx=5,
            rowspan=5,
        )

        # Length and Velocity
        length_frame = ttk.Frame(susc_frame, borderwidth=1, relief='solid')
        velocity_frame = ttk.Frame(susc_frame, borderwidth=1, relief='solid')

        for ind, f in enumerate([length_frame, velocity_frame], 1):
            f.grid(row=0, column=ind, padx=5, rowspan=3)

        ttk.Label(length_frame, text='Length').grid(row=0, column=0, columnspan=3)
        ttk.Label(velocity_frame, text='Velocity').grid(row=0, column=0, columnspan=3)

        self.susc_dp_vars = [tk.BooleanVar(value=False) for _ in self.dp_labels]
        for ind, label in enumerate(self.dp_labels[:3]):
            ttk.Label(length_frame, text=label).grid(row=1, column=ind)
            ttk.Checkbutton(length_frame, variable=self.susc_dp_vars[ind]).grid(row=2, column=ind)

        for ind, label in enumerate(self.dp_labels[3:]):
            ttk.Label(velocity_frame, text=label).grid(row=1, column=ind)
            ttk.Checkbutton(velocity_frame, variable=self.susc_dp_vars[ind + 3]).grid(row=2, column=ind)

        # Real and/or Complex
        self.hover_widget(ttk.Label, susc_frame, text='Real').grid(row=0, column=3, padx=5)
        self.real_susc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(susc_frame, variable=self.real_susc_var).grid(row=0, column=4)

        self.hover_widget(ttk.Label, susc_frame, text='Complex').grid(row=1, column=3, padx=5)
        self.complex_susc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(susc_frame, variable=self.complex_susc_var, command=self.show_susc_cap_widgets).grid(
            row=1,
            column=4,
            padx=5,
        )

        # CAPs' strengths
        self.susc_cap_frame = ttk.Frame(susc_frame, borderwidth=1, relief='solid')
        self.hover_widget(ttk.Label, self.susc_cap_frame, text='CAP strength(s):').grid(row=0, column=0, columnspan=3)
        self.susc_cap_entries = []
        for ind in range(2):
            ttk.Label(self.susc_cap_frame, text=f'CAP {ind + 1}').grid(row=1, column=ind, padx=5)
            e = ttk.Entry(self.susc_cap_frame, width=10)
            e.grid(row=2, column=ind, padx=5)
            self.susc_cap_entries.append(e)

        self.show_susc_cap_widgets()

        # Other parameters
        susc_keywords_frame = ttk.Frame(susc_frame)
        susc_keywords_frame.grid(row=3, column=1, columnspan=10, rowspan=2)
        self.susc_kw_entry_labels = [
            'Ket Symmetry',
            'Minimal Photon Energy [au]',
            'Maximum Photon Energy [au]',
            'Number of Energy points',
        ]
        self.hover_widget(
            ttk.Label,
            susc_keywords_frame,
            text=self.susc_kw_entry_labels[0],
            hover_text=self.KET_SYM_HOVER_TEXT,
        ).grid(row=0, column=0, padx=5)
        for ind, label in enumerate(self.susc_kw_entry_labels[1:], 1):
            ttk.Label(susc_keywords_frame, text=label).grid(row=0, column=ind, padx=5)

        self.susc_kw_entries = []
        for ind in range(4):
            e = ttk.Entry(susc_keywords_frame, width=5)
            e.grid(row=1, column=ind)
            self.susc_kw_entries.append(e)

    def show_susc_cap_widgets(self) -> None:
        """Toggle susceptibility CAP inputs depending on selected options."""
        if self.complex_susc_var.get() and not self.complex_h_var.get():
            self.susc_cap_frame.grid(row=0, column=5, rowspan=3)
        else:
            self.susc_cap_frame.grid_forget()

    def erase(self) -> None:
        """Reset all structural configuration widgets."""
        self.erase_cc_data()
        self.print_irrep()

        entries = [
            self.op_ket_sym_entry,
            self.dp_ket_sym_entry,
            self.h_ket_sym_entry,
            *self.h_cap_entries,
            *self.h_ecs_entries,
            *self.susc_cap_entries,
            *self.susc_kw_entries,
        ]
        for e in entries:
            e.delete(0, tk.END)

        variables = [
            *self.op_vars,
            *self.dp_vars,
            self.real_h_var,
            self.complex_h_var,
            self.ecs_h_var,
            self.real_susc_var,
            self.complex_susc_var,
            *self.susc_dp_vars,
        ]
        for c in variables:
            c.set(False)

        self.show_cap_radii([])

    def check_required_fields_and_files(self, operator_type: str, complex_calculation: bool = False) -> bool:
        """Ensure prerequisites exist for the requested structural calculation.

        Returns
        -------
        bool
            True when all required files and options are present.
        """
        required_files = {
            'sym_ops': ['store/log/ConvertDensityMatrics.out', 'store/log/ConvertIntegrals.out'],
            'dipoles': ['store/CloseCoupling/*_*/S'],
            'diag': ['store/CloseCoupling/*_*/H', 'store/CloseCoupling/*_*/S'],
            'susc': ['store/CloseCoupling/*_*/H'],
        }

        op_vals = [op.get() for op in self.op_vars]
        required_fields = {'sym_ops': [], 'dipoles': op_vals[:1], 'diag': op_vals[:2], 'susc': op_vals[:1]}

        r_files = required_files[operator_type]
        r_fields = required_fields[operator_type]

        if complex_calculation:
            r_files.append('store/CloseCoupling/*_*/CAP*')
            r_fields.append(op_vals[2])

        if operator_type == 'susc':
            for dp_ind, dp in enumerate(self.susc_dp_vars):
                if dp:
                    r_files.append(
                        f'store/CloseCoupling/*_*/{self.dp_labels[dp_ind].upper()}',
                    )
                    r_fields.append(self.dp_vars[dp_ind].get())

        if all(r_fields):
            return True

        for r_file in r_files:
            if not Path().glob(r_file):
                missing_required_calculation_popup()
                return False

        return True

    def check_dipole_syms(
        self,
        dp_vars: list[bool],
        ket_syms: list[str],
        new_computed_syms: list[str],
        start_ind: int = 0,
    ) -> bool:
        """Verify that dipole combinations produce previously computed symmetries.

        Returns
        -------
        bool
            True if all selected dipoles map to existing symmetries.
        """
        ket_states = self.unpack_all_symmetry(ket_syms)
        for ket_state in ket_states:
            for dp_ind, dp in enumerate(dp_vars):
                if dp:
                    ket_mult, ket_sym = ket_state[0], ket_state[1:]
                    prod = self.sym.mult(self.sym.dipole[dp_ind], ket_sym)
                    if ket_mult + prod not in self.computed_syms + new_computed_syms:
                        missing_symmetry_popup(
                            sym=f"""{self.dp_labels[dp_ind + start_ind].upper()}
                                    * {ket_mult + ket_sym} = {ket_mult + prod}""",
                            root='strut',
                        )
                        return False
        return True

    def _append_symmetric_operator_commands(self, lines: list[str]) -> tuple[bool, list[str]]:
        """Validate and append selected symmetric operator commands.

        Returns
        -------
        tuple[bool, list[str]]
            A success flag and the new computed symmetries from this section.
        """
        base_command = 'astraBuildOperator -gif ASTRA.INP'
        op_vals = [op.get() for op in self.op_vars]
        if not any(op_vals):
            return True, []

        if not self.check_required_fields_and_files('sym_ops'):
            return False, []

        op_names = ','.join(self.op_labels[ind] for ind, op_val in enumerate(op_vals) if op_val)
        ket_sym = self.get_text_from_widget(self.op_ket_sym_entry).replace(' ', '')
        if not ket_sym:
            required_field_popup("Symmetric operators' ket symmetry")
            return False, []

        if not self.check_ket_sym(ket_sym, 'Symmetric operators', check_computed=False):
            return False, []

        lines.append(f'{base_command} -op {op_names} -ketsym {ket_sym}')
        new_computed_syms = self.unpack_all_symmetry(ket_sym.split(','))
        return True, new_computed_syms

    def _append_dipole_commands(
        self,
        lines: list[str],
        check_ket_sym: Callable[[str, str], bool],
        check_dipole_syms: Callable[..., bool],
    ) -> bool:
        """Validate and append selected dipole operator commands.

        Returns
        -------
        bool
            True when all dipole command validations pass.
        """
        base_command = 'astraBuildOperator -gif ASTRA.INP --bf'
        dp_vals = [dp.get() for dp in self.dp_vars]
        if not any(dp_vals):
            return True

        if not self.check_required_fields_and_files('dipoles'):
            return False

        ket_sym = self.get_text_from_widget(self.dp_ket_sym_entry)
        if not ket_sym:
            required_field_popup("Dipoles' ket symmetry")
            return False

        if not check_ket_sym(ket_sym, "Dipoles'"):
            return False

        if any(dp_vals[:3]):
            if not check_dipole_syms(dp_vals[:3], ket_sym.split(',')):
                return False

            dp_length_vals = ','.join(self.dp_labels[ind] for ind in range(3) if dp_vals[ind])
            lines.append(f'{base_command} -op {dp_length_vals} -ketsym {ket_sym}')

        if any(dp_vals[3:]):
            if not check_dipole_syms(dp_vals[3:], ket_sym.split(','), start_ind=3):
                return False

            dp_velocity_vals = ','.join(self.dp_labels[ind] for ind in range(3, 6) if dp_vals[ind])
            lines.append(f'{base_command} -op {dp_velocity_vals} -ketsym {ket_sym}')

        return True

    def _append_hamiltonian_commands(
        self,
        lines: list[str],
        check_ket_sym: Callable[[str, str], bool],
    ) -> tuple[bool, list[bool], str]:
        """Validate and append Hamiltonian diagonalization commands.

        Returns
        -------
        tuple[bool, list[bool], str]
            A success flag, Hamiltonian mode selections, and CAP strengths text.
        """
        base_command = 'astraCondition -gif ASTRA.INP --bf'
        cap_strengths = ''
        h_vals = [self.real_h_var.get(), self.complex_h_var.get(), self.ecs_h_var.get()]
        if not any(h_vals):
            return True, h_vals, cap_strengths

        ket_sym = self.get_text_from_widget(self.h_ket_sym_entry)
        if not ket_sym:
            required_field_popup("Hamiltonian's diagonalization ket symmetry")
            return False, h_vals, cap_strengths

        if not check_ket_sym(ket_sym, "Hamiltonian's diagonalization"):
            return False, h_vals, cap_strengths

        if not self.check_required_fields_and_files('diag', complex_calculation=h_vals[1]):
            return False, h_vals, cap_strengths

        if h_vals[0]:
            lines.append(f'{base_command} -sym {ket_sym}')

        if h_vals[1]:
            cap_strengths = ','.join(self.get_caps_from_entries(self.h_cap_entries))
            if not cap_strengths:
                required_field_popup('Cap strength for diagonalization')
                return False, h_vals, cap_strengths

            append_complex_h = True
            missing_computed_cap_syms = self.check_already_computed_cap_strengths(cap_strengths, ket_sym)
            if not missing_computed_cap_syms:
                if not messagebox.askyesno(
                    'Warning!',
                    'This CAP strength has already been computed. Do you want to compute it again?',
                ):
                    self.complex_h_var.set(False)
                    self.show_h_cap_widgets()
                    append_complex_h = False
            elif len(missing_computed_cap_syms) != len(self.unpack_all_symmetry(ket_sym.split(','))) and not (
                messagebox.askyesno(
                    'Warning!',
                    'This CAP strength has already been computed for some symmetries. Do you want to recompute them?',
                )
            ):
                ket_sym = ','.join(missing_computed_cap_syms)

            if append_complex_h:
                lines.append(f'{base_command} -sym {ket_sym} -cap {cap_strengths}')

        if h_vals[2]:
            ecs_command = 'astraECS -gif ASTRA.INP'
            if not (ecs_params := self.get_ecs_params_from_entries(self.h_ecs_entries)):
                required_field_popup('ECS parameters for diagonalization')
                return False, h_vals, cap_strengths

            ecs_radius = ecs_params[0]
            ecs_angle = ecs_params[1]
            lines.append(f'{ecs_command} -sym {ket_sym} -ECSradius {ecs_radius} -ECSangle {ecs_angle} --only_diag')

        return True, h_vals, cap_strengths

    def _append_susceptibility_mode_commands(
        self,
        lines: list[str],
        susc_dp_vals: list[bool],
        susc_entries: list[str],
        cap_text: str,
        check_dipole_syms: Callable[..., bool],
    ) -> bool:
        """Append dipole transition and susceptibility commands for one CAP mode.

        Returns
        -------
        bool
            True when command generation for the selected mode succeeds.
        """
        if any(susc_dp_vals[:3]):
            if not check_dipole_syms(susc_dp_vals[:3], susc_entries[0].split(',')):
                return False

            susc_dp_length_vals = ','.join(self.dp_labels[ind] for ind in range(3) if susc_dp_vals[ind])
            lines.extend([
                (
                    f'astraDipoleTransition -gif ASTRA.INP -op {susc_dp_length_vals} '
                    f'-ketsym {susc_entries[0]} -trans bb {cap_text}'
                ),
                (
                    f'astraSusceptibility -gif ASTRA.INP -op {susc_dp_length_vals} '
                    f'-ketsym {susc_entries[0]} -trans bb -emin {susc_entries[1]} '
                    f'-emax {susc_entries[2]} -ne {susc_entries[3]} {cap_text}'
                ),
            ])

        if any(susc_dp_vals[3:]):
            if not check_dipole_syms(susc_dp_vals[3:], susc_entries[0].split(','), start_ind=3):
                return False

            susc_dp_velocity_vals = ','.join(self.dp_labels[ind] for ind in range(3, 6) if susc_dp_vals[ind])
            lines.extend([
                (
                    f'astraDipoleTransition -gif ASTRA.INP -op {susc_dp_velocity_vals} '
                    f'-ketsym {susc_entries[0]} -trans bb {cap_text}'
                ),
                (
                    f'astraSusceptibility -gif ASTRA.INP -op {susc_dp_velocity_vals} '
                    f'-ketsym {susc_entries[0]} -trans bb -emin {susc_entries[1]} '
                    f'-emax {susc_entries[2]} -ne {susc_entries[3]} {cap_text}'
                ),
            ])

        return True

    def _append_susceptibility_commands(
        self,
        lines: list[str],
        check_ket_sym: Callable[[str, str], bool],
        check_dipole_syms: Callable[..., bool],
        h_vals: list[bool],
        cap_strengths: str,
    ) -> bool:
        """Validate and append susceptibility-related commands.

        Returns
        -------
        bool
            True when susceptibility command generation succeeds.
        """
        susc_dp_vals = [susc_dp.get() for susc_dp in self.susc_dp_vars]
        susc_real_complex = [self.real_susc_var.get(), self.complex_susc_var.get()]
        susc_entries = [self.get_text_from_widget(e) for e in self.susc_kw_entries]
        if not any(susc_real_complex) and not any(susc_dp_vals):
            return True

        if not any(susc_dp_vals) and any(susc_real_complex):
            required_field_popup('Susceptibility dipoles')
            return False

        if any(susc_dp_vals) and not any(susc_real_complex):
            required_field_popup('Susceptibility real and/or complex')
            return False

        if not self.check_required_fields_and_files('susc', complex_calculation=susc_real_complex[1]):
            return False

        for e_ind, entry_val in enumerate(susc_entries):
            if not entry_val:
                required_field_popup(self.susc_kw_entry_labels[e_ind])
                return False

        if not check_ket_sym(susc_entries[0], 'Susceptibility'):
            return False

        for real_complex, use_cap in zip(susc_real_complex, [False, True]):
            if not real_complex:
                continue

            current_cap_text = ''
            if use_cap:
                if not h_vals[1]:
                    current_cap_text = ','.join(self.get_caps_from_entries(self.susc_cap_entries))
                    if not current_cap_text:
                        required_field_popup('Cap strength for susceptibility')
                        return False

                    if self.check_already_computed_cap_strengths(current_cap_text, susc_entries[0]):
                        if messagebox.askokcancel(
                            'Error!',
                            'This CAP strength has not been computed for this symmetry. '
                            'Do you want to run a diagonalization routine for it?',
                        ):
                            self.complex_h_var.set(True)
                            self.h_ket_sym_entry.delete(0, tk.END)
                            self.h_ket_sym_entry.insert(0, susc_entries[0])

                            for cap_entry, cap_value in zip(
                                self.h_cap_entries,
                                current_cap_text.split(','),
                            ):
                                cap_entry.delete(0, tk.END)
                                cap_entry.insert(0, cap_value)

                            self.show_h_cap_widgets()
                            self.save()  # Recompute the commands
                        return False
                else:
                    current_cap_text = cap_strengths

                current_cap_text = '-cap ' + current_cap_text

            if not self._append_susceptibility_mode_commands(
                lines,
                susc_dp_vals,
                susc_entries,
                current_cap_text,
                check_dipole_syms,
            ):
                return False

        return True

    def get_commands(self) -> str:
        """Assemble the command string for the selected structural tasks.

        Returns
        -------
        str
            Script content ready to be written to disk.
        """
        lines: list[str] = []
        ok, new_computed_syms = self._append_symmetric_operator_commands(lines)
        if not ok:
            return ''

        check_ket_sym = partial(self.check_ket_sym, new_computed_syms=new_computed_syms)
        check_dipole_syms = partial(self.check_dipole_syms, new_computed_syms=new_computed_syms)

        if not self._append_dipole_commands(lines, check_ket_sym, check_dipole_syms):
            return ''

        ok, h_vals, cap_strengths = self._append_hamiltonian_commands(lines, check_ket_sym)
        if not ok:
            return ''

        if not self._append_susceptibility_commands(
            lines,
            check_ket_sym,
            check_dipole_syms,
            h_vals,
            cap_strengths,
        ):
            return ''

        return self.add_idle_thread_and_join_lines(lines)

    def check_already_computed_cap_strengths(self, cap_strengths_str: str, ket_sym_str: str) -> list:
        """Return ket symmetries whose CAP strengths still need evaluation.

        Returns
        -------
        list
            Symmetry labels missing the requested CAP strengths.
        """
        ket_syms = self.unpack_all_symmetry(ket_sym_str.split(','))

        cap_strengths = cap_strengths_str.split(',')
        cap_strengths = [float(cap_strength) for cap_strength in cap_strengths]

        computed_cap_strengths = self.notebook.get_cap_strengths(group_syms=False, return_float=True)

        not_computed_cap_strengths_syms = []

        for ket_sym in ket_syms:
            if cap_strengths not in computed_cap_strengths.get(ket_sym, []):
                not_computed_cap_strengths_syms.append(ket_sym)  # noqa: PERF401

        return not_computed_cap_strengths_syms

    def load(self) -> None:
        """Populate widgets using the saved structural script."""
        lines = self.get_script_lines()

        if not lines:
            return

        for line in lines:
            # Check for symmetric operators and dipoles
            if 'astraBuildOperator' in line:
                sym_op_flag = False
                dp_op_flag = False
                ops = self.get_keyword_from_line(line, '-op').split(',')

                # Checks for symmetric operators
                for ind, sym_op in enumerate(self.op_labels):
                    if sym_op in ops:
                        sym_op_flag = True
                        self.op_vars[ind].set(True)
                if sym_op_flag:
                    self.op_ket_sym_entry.insert(
                        0,
                        self.get_keyword_from_line(line, '-ketsym'),
                    )
                    continue

                # Checks for dipole operators
                for ind, dp_label in enumerate(self.dp_labels):
                    if dp_label in ops:
                        dp_op_flag = True
                        self.dp_vars[ind].set(True)
                if dp_op_flag:
                    self.dp_ket_sym_entry.delete(0, tk.END)
                    self.dp_ket_sym_entry.insert(
                        0,
                        self.get_keyword_from_line(line, '-ketsym'),
                    )

            # Check for diagonalization of the hamiltonian
            elif 'astraCondition' in line:
                self.h_ket_sym_entry.delete(0, tk.END)
                self.h_ket_sym_entry.insert(0, self.get_keyword_from_line(line, '-sym'))

                if caps := self.get_caps_from_line(line):
                    self.complex_h_var.set(True)
                    for ind, cap in enumerate(caps):
                        self.h_cap_entries[ind].delete(0, tk.END)
                        self.h_cap_entries[ind].insert(0, cap)
                else:
                    self.real_h_var.set(True)

            elif 'astraECS' in line:
                if ecs_params := self.get_ecs_params_from_line(line):
                    self.ecs_h_var.set(True)
                    for ind, param in enumerate(ecs_params):
                        self.h_ecs_entries[ind].delete(0, tk.END)
                        self.h_ecs_entries[ind].insert(0, param)
                    self.show_h_ecs_widgets()

            elif 'astraSusceptibility' in line:
                for ind, keyword in enumerate(['-ketsym', '-emin', '-emax', '-ne']):
                    self.susc_kw_entries[ind].delete(0, tk.END)
                    self.susc_kw_entries[ind].insert(
                        0,
                        self.get_keyword_from_line(line, keyword),
                    )

                for ind, dp_label in enumerate(self.dp_labels):
                    if dp_label in line:
                        self.susc_dp_vars[ind].set(True)

                if caps := self.get_caps_from_line(line):
                    self.complex_susc_var.set(True)
                    for ind, cap in enumerate(caps):
                        self.susc_cap_entries[ind].delete(0, tk.END)
                        self.susc_cap_entries[ind].insert(0, cap)
                else:
                    self.real_susc_var.set(True)

        self.show_h_cap_widgets()
        self.show_susc_cap_widgets()

    def get_outputs(self) -> None:
        """Refresh computed symmetries and CAP strengths in the UI."""
        self.show_computed_syms()
        self.notebook.show_cap_strengths()
